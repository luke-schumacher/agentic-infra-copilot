# Data Recovery & Setup Documentation

## Summary
The PDF files from `~/Documents/GitHub/agent_files` have been successfully copied back to the project. However, the hardware agent loader code needs to be updated to actually load and index them.

## What Was Done

### 1. PDF Files Restored ✅
**Source**: `~/Documents/GitHub/agent_files/`
**Destination**: `data/raw/siemens/magnetom_pdfs/`

**Files copied** (51 total PDFs, 316MB):
- ✅ MR Safety Guidelines (5.7MB) → `safety/`
- ✅ Installation Manual (111MB) → `hardware/`  
- ✅ 9 Operator Manuals (Body MR, Cardiac MR, Neuro MR, etc.) → `hardware/`
- ✅ Multiple Addendum PDFs (Pulse Sequences, Keyboard Shortcuts, etc.) → `hardware/`
- ✅ Additional system documentation → `hardware/`

### 2. Current Status
- **Raw files**: 563 files in `data/raw/siemens/`
- **Indexed in ChromaDB**: Only 119 docs (hardware agent)
- **Problem**: Code only loads 4 DCS PDFs, ignoring the 51 PDFs in `magnetom_pdfs/`

## Why PDFs Are Not Indexed

The file `src/agents/hardware_agent/mri_hardware_loader.py` has a function `load_dcs_documentation()` (line 340) that ONLY loads PDFs matching these patterns:

```python
DCS_PDF_PATTERNS = [
    'DCS_MR_XA50', 'DCS_MR_XA51A', 'DCS_MR_XA60',
    'MAGNETOM_SOLA_CSPL', 'MAGNETOM Sola CSPL'
]
```

It does NOT scan the `magnetom_pdfs/hardware/` or `magnetom_pdfs/safety/` directories.

## Expected Document Counts (from your previous build)

According to your logs from before the litellm fix:
- **Hardware agent**: 2,682 documents
  - DCS PDFs: 1,320 chunks
  - Operator manuals: 1,243 chunks  
  - Event logs: ~119 chunks
- **Telemetry agent**: Higher count (includes safety PDFs)
- **Governance agent**: 418 documents

## Next Steps Required

### Option 1: Update the loader code (recommended)
Add a function to load operator manuals and safety PDFs from `magnetom_pdfs/`:

```python
def load_operator_manuals(self) -> List[Document]:
    """Load operator manual PDFs from magnetom_pdfs directory."""
    hardware_dir = self.raw_pdf_dir / "magnetom_pdfs" / "hardware"
    
    if not hardware_dir.exists():
        logger.warning(f"Hardware manuals directory not found: {hardware_dir}")
        return []
    
    pdf_files = list(hardware_dir.glob("*.pdf"))
    logger.info(f"Loading {len(pdf_files)} operator manual PDFs from {hardware_dir}")
    
    # Same chunking logic as load_dcs_documentation()
    ...
```

Then call it in the `load()` method.

### Option 2: Use git stash to restore ChromaDB (temporary)
The indexed ChromaDB with 2,682 docs is in `stash@{1}`:
```bash
git stash show stash@{1} --stat | grep chroma
# hardware_agent/chroma.sqlite3 should be 35MB
```

But this is NOT sustainable - you need the code fix.

## Important Notes

### Why PDFs Aren't in Git
PDFs are in `.gitignore` (`*.pdf` pattern). This is correct for large binary files.

**To preserve PDFs across machines:**
1. Keep `agent_files/` directory as your source
2. Document the copy process (this file)
3. Or use Git LFS for large files
4. Or commit a setup script that copies from `agent_files/`

### ChromaDB Permission Issues
Some ChromaDB files are owned by `root` (Docker containers). To clean:
```bash
docker-compose down
sudo rm -rf chroma_db/*
docker-compose up --build
```

## File Locations Reference

```
~/Documents/GitHub/
├── agent_files/              # SOURCE (preserve this!)
│   ├── *.pdf                 # 291 PDFs, ~2.6GB
│   ├── 2026-02/             # 856MB
│   └── Wissensbasis/        # 1.8GB
│
└── agentic-infra-copilot/
    └── data/raw/siemens/
        ├── *.pdf            # 4 DCS PDFs (currently loaded)
        └── magnetom_pdfs/
            ├── hardware/     # 48 PDFs (NOT loaded yet)
            └── safety/       # 3 PDFs (NOT loaded yet)
```

## Recovery Commands

If PDFs get lost again:

```bash
cd /home/lukeschumacher/Documents/GitHub/agentic-infra-copilot

# Copy safety PDFs
cp ~/Documents/GitHub/agent_files/Guidelines*.pdf \
   data/raw/siemens/magnetom_pdfs/safety/

# Copy hardware PDFs
cp ~/Documents/GitHub/agent_files/Installation*.pdf \
   ~/Documents/GitHub/agent_files/Operator_Manual*.pdf \
   ~/Documents/GitHub/agent_files/Addendum*.pdf \
   ~/Documents/GitHub/agent_files/Additional*.pdf \
   ~/Documents/GitHub/agent_files/Image_System*.pdf \
   data/raw/siemens/magnetom_pdfs/hardware/

# Verify
find data/raw/siemens/magnetom_pdfs -name "*.pdf" | wc -l
# Should show 51

# Rebuild with fresh index
docker-compose down
sudo rm -rf chroma_db/*
docker-compose up --build
```

## Contact Previous Session

According to your notes, you had this working with 2,682 documents. The code changes that added operator manual loading were likely:
1. In a branch that wasn't merged
2. Lost during the stash operations
3. Or in local uncommitted changes

Check:
- Other branches: `feature/data-ingestion-pipelines`
- Git history around the dates you saw 2,682 docs
- Your `notes.md` or session logs for code snippets

---
Generated: 2026-03-31
Session: Fixing Azure API + Data Recovery
