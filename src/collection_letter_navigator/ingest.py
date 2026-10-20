"""Offline ingestion: statute XML to metadata-rich, section-sized chunks.

Reads the official XML of *gesetze-im-internet.de* for the laws in
``data/kb_scope.yaml``, cuts it into one chunk per section (splitting long
sections by subsection), attaches the metadata the retrieval filter needs and
writes the Chroma index plus its manifest. The ID scheme is deterministic so
that two runs on the same XML produce the same chunks (FR-04 AC5).

Related: FR-04, FR-06 AC1, FR-21 AC6, NFR-10, §9
"""

from __future__ import annotations

import io
import json
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from pathlib import Path

import yaml
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from collection_letter_navigator import config, llm

#: Default download cache for the statute XML (gitignored, see .gitignore).
RAW_DIR: Path = config.DATA_DIR / "raw"

#: Section label inside an ``<enbez>`` element, e.g. "§ 703a" -> "703a" (FR-04 AC1).
_SECTION_LABEL = re.compile(r"§\s*(\d+[a-z]?)")

#: Subsection marker at the start of a paragraph, e.g. "(2) Die ..." -> "2" (FR-04 AC2).
_SUBSECTION_LABEL = re.compile(r"^\((\d+[a-z]?)\)\s*")

#: Timeout for the statute download in seconds (NFR-02).
_DOWNLOAD_TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# Scope (FR-04 AC1)
# ---------------------------------------------------------------------------


def load_kb_scope(path: Path | None = None) -> dict[str, list[str]]:
    """Read the list of provisions to index.

    Entries are single section labels (``"247"``) or inclusive ranges
    (``"688-703d"``); ranges are resolved later in document order by
    :func:`expand_scope`, so lettered sections need not be listed one by one.

    Args:
        path: Scope file; defaults to :data:`config.KB_SCOPE_PATH`.

    Returns:
        A mapping from law code (``"BGB"``, ``"ZPO"``, ``"RDG"``) to its scope
        entries, e.g. ``{"ZPO": ["222", "688-703d"]}``. Laws with an empty list
        are left out.

    Raises:
        FileNotFoundError: If the scope file does not exist.
        ValueError: If the file names a law outside :data:`config.KB_LAWS`.

    Related: FR-04 AC1
    """
    scope_path = path or config.KB_SCOPE_PATH
    raw = yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}
    unknown = sorted(set(raw) - set(config.KB_LAWS))
    if unknown:
        raise ValueError(f"Unknown law code(s) in {scope_path.name}: {', '.join(unknown)}")
    return {law: [str(entry) for entry in entries] for law, entries in raw.items() if entries}


def expand_scope(entries: list[str], available: list[str]) -> list[str]:
    """Resolve scope entries against the sections that exist, in document order.

    Args:
        entries: Section labels and ranges from :func:`load_kb_scope`.
        available: All section labels of the law, in the order of the XML.

    Returns:
        The selected section labels, in document order, without duplicates.

    Raises:
        ValueError: If a label or a range boundary does not exist in the XML.

    Related: FR-04 AC1
    """
    selected: set[str] = set()
    position = {label: i for i, label in enumerate(available)}
    for entry in entries:
        start, _, end = entry.partition("-")
        end = end or start
        missing = [label for label in (start, end) if label not in position]
        if missing:
            raise ValueError(f"Section(s) not found in the XML: {', '.join(missing)}")
        selected.update(available[position[start] : position[end] + 1])
    return [label for label in available if label in selected]


# ---------------------------------------------------------------------------
# Download (FR-04 AC1)
# ---------------------------------------------------------------------------


def download_law_xml(law: str, *, cache_dir: Path | None = None, refresh: bool = False) -> Path:
    """Download the statute XML, or return the cached copy.

    Args:
        law: Law code, one of :data:`config.KB_LAWS`.
        cache_dir: Where downloads are cached; defaults to ``data/raw/``.
        refresh: Download again even if a cached copy exists.

    Returns:
        Path to the XML file on disk (``data/raw/<law>/<file>.xml``).

    Raises:
        RuntimeError: If the download fails and no cached copy exists.

    Related: FR-04 AC1
    """
    target = (cache_dir or RAW_DIR) / law.lower()
    cached = sorted(target.glob("*.xml"))
    if cached and not refresh:
        return cached[0]

    url = f"{config.GESETZE_IM_INTERNET_BASE_URL}/{law.lower()}/xml.zip"
    try:
        with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            payload = response.read()
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(target)
    except (OSError, zipfile.BadZipFile) as error:
        if cached:
            return cached[0]
        raise RuntimeError(f"Could not download {url}: {error}") from error

    extracted = sorted(target.glob("*.xml"))
    if not extracted:
        raise RuntimeError(f"No XML file found in the archive from {url}")
    return extracted[0]


# ---------------------------------------------------------------------------
# Parsing and chunking (FR-04 AC1-AC3, AC5)
# ---------------------------------------------------------------------------


def _clean(text: str) -> str:
    """Collapse whitespace, including the line breaks of the XML layout."""
    return re.sub(r"\s+", " ", text).strip()


#: XML elements that separate words (list items, line breaks); inline markup does not.
_BLOCK_TAGS = frozenset({"DL", "DT", "DD", "LA", "BR", "Table", "row", "entry"})


def _element_text(element: ET.Element) -> str:
    """Return the text of an element, with spaces around block-level children."""
    parts = [element.text or ""]
    for child in element:
        separator = " " if child.tag in _BLOCK_TAGS else ""
        parts += [separator, _element_text(child), separator, child.tail or ""]
    return "".join(parts)


def _paragraphs(norm: ET.Element) -> list[str]:
    """Return the text of every top-level ``<P>`` of a norm, footnotes excluded."""
    content = norm.find("./textdaten/text/Content")
    if content is None:
        return []
    texts = [_clean(_element_text(p)) for p in content.findall("P")]
    return [text for text in texts if text]


def _build_date(root: ET.Element, xml_path: Path) -> date:
    """Version date of the statute XML (``builddate``), else the file date."""
    stamp = root.get("builddate", "")
    if len(stamp) >= 8 and stamp[:8].isdigit():
        return date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
    return date.fromtimestamp(xml_path.stat().st_mtime)


def section_source_url(law: str, section: str) -> str:
    """Build the public link to one provision.

    Args:
        law: Law code.
        section: Section label.

    Returns:
        The URL of the provision on *gesetze-im-internet.de*, e.g.
        ``https://www.gesetze-im-internet.de/bgb/__195.html``.

    Related: FR-04 AC3, FR-08 AC2
    """
    return f"{config.GESETZE_IM_INTERNET_BASE_URL}/{law.lower()}/__{section}.html"


def parse_law_xml(
    xml_path: Path,
    law: str,
    scope: list[str],
    retrieved_at: date | None = None,
) -> list[Document]:
    """Parse one statute XML into one document per section in scope.

    Args:
        xml_path: Path to the statute XML.
        law: Law code the file belongs to.
        scope: Scope entries (labels or ranges) for this law, see :func:`expand_scope`.
        retrieved_at: Snapshot date; defaults to the ``builddate`` of the XML,
            i.e. the date of the published version of the statute.

    Returns:
        One document per section, carrying ``law``, ``section``, ``title``,
        ``source_url`` and ``retrieved_at`` metadata. The text keeps one line per
        ``<P>`` element so that :func:`chunk_section` can split by subsection.

    Raises:
        ValueError: If a section in ``scope`` is missing from the XML.

    Related: FR-04 AC1, FR-04 AC3
    """
    root = ET.parse(xml_path).getroot()
    snapshot = retrieved_at or _build_date(root, xml_path)
    sections: dict[str, tuple[str, list[str]]] = {}
    order: list[str] = []
    for norm in root.iter("norm"):
        enbez = norm.findtext("./metadaten/enbez") or ""
        match = _SECTION_LABEL.match(enbez.strip())
        if match is None or match.group(1) in sections:
            continue  # headings, preamble, annexes or a repeated label
        label = match.group(1)
        title = _clean(norm.findtext("./metadaten/titel") or "")
        sections[label] = (title, _paragraphs(norm))
        order.append(label)

    documents = []
    for label in expand_scope(scope, order):
        title, paragraphs = sections[label]
        documents.append(
            Document(
                page_content="\n".join(paragraphs),
                metadata={
                    "law": law,
                    "section": label,
                    "title": title,
                    "source_url": section_source_url(law, label),
                    "retrieved_at": snapshot.isoformat(),
                },
            )
        )
    return documents


def make_chunk_id(law: str, section: str, subsection: str | None) -> str:
    """Build the stable identifier of one chunk.

    The ID depends only on law, section and subsection, so that re-running the
    ingestion yields the same IDs (FR-04 AC5) and the answer call can cite a
    chunk the UI can look up (FR-08 AC2).

    Args:
        law: Law code.
        section: Section label, e.g. ``"692"``.
        subsection: Subsection label, or None for a whole section.

    Returns:
        The chunk ID, e.g. ``"ZPO-692"`` or ``"ZPO-692-1"``.

    Related: FR-04 AC5, FR-08 AC2
    """
    return f"{law}-{section}" if subsection is None else f"{law}-{section}-{subsection}"


def _with_heading(meta: dict[str, str], body: str, subsection: str | None) -> str:
    """Prefix the chunk text with law, section and title (helps short sections)."""
    heading = f"§ {meta['section']} {meta['law']} {meta['title']}".strip()
    if subsection is not None:
        heading += f" – Absatz {subsection}"
    return f"{heading}\n{body}"


def chunk_section(section: Document, max_characters: int | None = None) -> list[Document]:
    """Split one section into chunks without crossing the section boundary.

    A section shorter than the limit stays one chunk; a longer one is split by
    subsection (*Absatz*), and each part keeps the section metadata plus its
    ``subsection`` label. Chroma does not store None, so a whole-section chunk
    has ``subsection = ""``.

    Args:
        section: The section document produced by :func:`parse_law_xml`.
        max_characters: Split threshold; defaults to
            :data:`config.MAX_CHUNK_CHARACTERS`.

    Returns:
        One or more chunk documents, each with a deterministic ``chunk_id``
        in its metadata and as its ``id``.

    Related: FR-04 AC2, FR-04 AC3
    """
    limit = max_characters or config.MAX_CHUNK_CHARACTERS
    meta = {key: str(value) for key, value in section.metadata.items()}
    paragraphs = section.page_content.split("\n")

    if len(section.page_content) <= limit or len(paragraphs) == 1:
        parts: list[tuple[str | None, str]] = [(None, section.page_content)]
    else:
        parts = []
        for number, paragraph in enumerate(paragraphs, start=1):
            match = _SUBSECTION_LABEL.match(paragraph)
            parts.append((match.group(1) if match else str(number), paragraph))

    chunks = []
    for subsection, body in parts:
        chunk_id = make_chunk_id(meta["law"], meta["section"], subsection)
        chunks.append(
            Document(
                id=chunk_id,
                page_content=_with_heading(meta, body, subsection),
                metadata={**meta, "subsection": subsection or "", "chunk_id": chunk_id},
            )
        )
    return chunks


def build_chunks(
    scope: dict[str, list[str]],
    *,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> list[Document]:
    """Run the whole ingestion for every law in scope.

    Args:
        scope: Mapping from law code to scope entries, see :func:`load_kb_scope`.
        cache_dir: Where downloads are cached; defaults to ``data/raw/``.
        refresh: Download the XML again instead of using the cache.

    Returns:
        Every chunk of the knowledge base, in a deterministic order (laws as in
        :data:`config.KB_LAWS`, sections in document order).

    Related: FR-04 AC1, FR-04 AC2, FR-04 AC5
    """
    chunks: list[Document] = []
    for law in (law for law in config.KB_LAWS if law in scope):
        xml_path = download_law_xml(law, cache_dir=cache_dir, refresh=refresh)
        for section in parse_law_xml(xml_path, law, scope[law]):
            chunks.extend(chunk_section(section))
    return chunks


# ---------------------------------------------------------------------------
# Index and manifest (FR-04 AC4, AC6, FR-21 AC6)
# ---------------------------------------------------------------------------


def write_index(
    chunks: list[Document],
    index_dir: Path | None = None,
    embeddings: Embeddings | None = None,
) -> None:
    """Embed the chunks and persist the Chroma index.

    The target directory is rebuilt from scratch, so the index always matches the
    chunks exactly (FR-04 AC5).

    Args:
        chunks: The chunks to index; each must carry its ``id``.
        index_dir: Target directory; defaults to :data:`config.INDEX_DIR`.
        embeddings: Embedding client; defaults to :func:`llm.build_embeddings`.
            Tests pass a fake here.

    Returns:
        None.

    Raises:
        RuntimeError: If embedding fails; a partial index is not left behind.

    Related: FR-04 AC4, FR-04 AC6
    """
    target = index_dir or config.INDEX_DIR
    if target.exists():
        shutil.rmtree(target)
    try:
        store = Chroma(  # AI: the vector store keeps one embedding per chunk
            collection_name=config.CHROMA_COLLECTION_NAME,
            embedding_function=embeddings or llm.build_embeddings(),  # AI: same model as queries
            persist_directory=str(target),
        )
        store.add_documents(chunks, ids=[str(chunk.id) for chunk in chunks])  # AI: embeds here
    except Exception as error:
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(f"Embedding failed, no index was written: {error}") from error


def write_manifest(
    chunks: list[Document],
    index_dir: Path | None = None,
    embedding_model: str | None = None,
    built_at: str | None = None,
) -> None:
    """Write the index manifest shown in the UI.

    Args:
        chunks: The indexed chunks, used for counts and dates per law.
        index_dir: Target directory; defaults to :data:`config.INDEX_DIR`.
        embedding_model: Model used for the index; defaults to
            :data:`config.EMBEDDING_MODEL`.
        built_at: Build time to record; defaults to now. Passed when only the
            manifest is rewritten for an unchanged index.

    Returns:
        None. The manifest holds ``snapshot_dates`` (version date per law, from
        the chunks' ``retrieved_at``) and ``snapshot_date`` (the most recent of
        them).

    Related: FR-04 AC4, FR-21 AC6, NFR-10
    """
    target = index_dir or config.INDEX_DIR
    target.mkdir(parents=True, exist_ok=True)
    per_law: dict[str, int] = {}
    dates: dict[str, str] = {}
    for chunk in chunks:
        law = str(chunk.metadata["law"])
        per_law[law] = per_law.get(law, 0) + 1
        dates[law] = max(dates.get(law, ""), str(chunk.metadata["retrieved_at"]))
    manifest = {
        "snapshot_date": max(dates.values(), default=""),
        "snapshot_dates": dates,
        "embedding_model": embedding_model or config.EMBEDDING_MODEL,
        "built_at": built_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "chunk_count": len(chunks),
        "chunks_per_law": per_law,
        "chunk_ids": [str(chunk.id) for chunk in chunks],
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def read_manifest(index_dir: Path | None = None) -> dict[str, object]:
    """Read the manifest of the committed index.

    Args:
        index_dir: Index directory; defaults to :data:`config.INDEX_DIR`.

    Returns:
        The manifest contents: snapshot date, embedding model and chunk counts.

    Raises:
        FileNotFoundError: If the index has not been built.

    Related: FR-04 AC4, FR-21 AC6
    """
    path = (index_dir or config.INDEX_DIR) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No index manifest at {path}; run scripts/build_index.py first")
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data
