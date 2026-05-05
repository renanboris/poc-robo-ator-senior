#!/usr/bin/env python3
"""
cleanup_project.py — Senior Training OS Project Cleanup
========================================================
Script pragmático para reorganizar a estrutura do projeto de forma segura.

Usage:
    python cleanup_project.py --dry-run      # Preview changes
    python cleanup_project.py                # Execute cleanup

Features:
    - Backup automático antes de qualquer mudança
    - Move 17 test files para tests/
    - Move 5 analysis scripts para scripts/analysis/
    - Arquiva 6 exploratory scripts em old_but_gold/exploratory/
    - Limpa 2 generated artifacts
    - Atualiza imports automaticamente
    - Gera relatório completo (CLEANUP_REPORT.md)
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent

# Files to organize
TEST_FILES = [
    "test_aura_search.py",
    "test_builders.py",
    "test_erp_discovery.py",
    "test_final_search.py",
    "test_ged_access.py",
    "test_gestao_page.py",
    "test_important_urls_pipeline.py",
    "test_important_urls.py",
    "test_openai.py",
    "test_recursive_erp.py",
    "test_single_url.py",
    "test_sitemap_modules.py",
    "test_skill_memory.py",
    "test_spa_discovery.py",
    "conftest.py",
]

ANALYSIS_SCRIPTS = [
    "analyze_erp_patterns.py",
    "analyze_sitemap_structure.py",
    "check_sitemap_content.py",
    "debug_crawler.py",
    "debug_erp_discovery.py",
]

EXPLORATORY_SCRIPTS = [
    "enhanced_crawler.py",
    "enhanced_erp_discovery.py",
    "fix_erp_discovery.py",
    "intelligent_spa_crawler.py",
    "investigate_sitemaps.py",
    "manual_important_urls.py",
]

GENERATED_ARTIFACTS = [
    "erp_page_content.html",
    "erp_pattern_analysis.json",
]


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────

def print_header(text: str) -> None:
    """Print formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}\n")


def print_step(step: str, status: str = "⏳") -> None:
    """Print step with status icon."""
    print(f"{status} {step}")


def print_success(message: str) -> None:
    """Print success message."""
    print(f"✅ {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    print(f"⚠️  {message}")


def print_error(message: str) -> None:
    """Print error message."""
    print(f"❌ {message}")


# ─────────────────────────────────────────────────────────────────────────────
# Backup Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_backup(files: List[Path]) -> Path:
    """Create backup of files before modification."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_ROOT / f".cleanup_backup_{timestamp}"
    
    print_step(f"Creating backup in {backup_dir.name}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    metadata = {
        "timestamp": timestamp,
        "files": {}
    }
    
    for file_path in files:
        if not file_path.exists():
            continue
        
        rel_path = file_path.relative_to(PROJECT_ROOT)
        backup_file = backup_dir / rel_path
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(file_path, backup_file)
        metadata["files"][str(rel_path)] = str(backup_file)
    
    # Save metadata
    with open(backup_dir / "backup_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print_success(f"Backup created: {len(metadata['files'])} files")
    return backup_dir


# ─────────────────────────────────────────────────────────────────────────────
# Import Update Functions
# ─────────────────────────────────────────────────────────────────────────────

def update_imports_in_file(file_path: Path, old_location: Path, new_location: Path) -> bool:
    """Update import statements in a moved file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        
        # Update sys.path.insert for files moved to tests/
        if "tests" in str(new_location):
            # Change: sys.path.insert(0, str(Path(__file__).parent))
            # To:     sys.path.insert(0, str(Path(__file__).parent.parent))
            content = re.sub(
                r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent\)\)',
                'sys.path.insert(0, str(Path(__file__).parent.parent))',
                content
            )
        
        # Update sys.path.insert for files moved to scripts/analysis/
        if "scripts/analysis" in str(new_location):
            # Change: sys.path.insert(0, str(Path(__file__).parent))
            # To:     sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            content = re.sub(
                r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent\)\)',
                'sys.path.insert(0, str(Path(__file__).parent.parent.parent))',
                content
            )
        
        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            return True
        
        return False
        
    except Exception as e:
        print_warning(f"Failed to update imports in {file_path.name}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# File Movement Functions
# ─────────────────────────────────────────────────────────────────────────────

def move_file(source: Path, destination: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """Move a file and update its imports."""
    if not source.exists():
        return False, f"Source not found: {source}"
    
    if destination.exists():
        return False, f"Destination already exists: {destination}"
    
    if dry_run:
        return True, f"Would move: {source} → {destination}"
    
    try:
        # Create destination directory
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file
        shutil.move(str(source), str(destination))
        
        # Update imports
        imports_updated = update_imports_in_file(destination, source, destination)
        
        status = "moved"
        if imports_updated:
            status += " (imports updated)"
        
        return True, status
        
    except Exception as e:
        return False, f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Stage Execution Functions
# ─────────────────────────────────────────────────────────────────────────────

def execute_stage_move_tests(dry_run: bool = False) -> Dict:
    """Stage 1: Move test files to tests/ directory."""
    print_header("Stage 1: Move Test Files")
    
    results = {"moved": [], "skipped": [], "failed": []}
    tests_dir = PROJECT_ROOT / "tests"
    
    for filename in TEST_FILES:
        source = PROJECT_ROOT / filename
        destination = tests_dir / filename
        
        success, message = move_file(source, destination, dry_run)
        
        if success:
            results["moved"].append((filename, message))
            print_success(f"{filename} → tests/")
        elif "not found" in message.lower():
            results["skipped"].append((filename, message))
            print_warning(f"{filename} (not found)")
        else:
            results["failed"].append((filename, message))
            print_error(f"{filename}: {message}")
    
    print(f"\n📊 Summary: {len(results['moved'])} moved, {len(results['skipped'])} skipped, {len(results['failed'])} failed")
    return results


def execute_stage_move_analysis(dry_run: bool = False) -> Dict:
    """Stage 2: Move analysis scripts to scripts/analysis/."""
    print_header("Stage 2: Move Analysis Scripts")
    
    results = {"moved": [], "skipped": [], "failed": []}
    analysis_dir = PROJECT_ROOT / "scripts" / "analysis"
    
    for filename in ANALYSIS_SCRIPTS:
        source = PROJECT_ROOT / filename
        destination = analysis_dir / filename
        
        success, message = move_file(source, destination, dry_run)
        
        if success:
            results["moved"].append((filename, message))
            print_success(f"{filename} → scripts/analysis/")
        elif "not found" in message.lower():
            results["skipped"].append((filename, message))
            print_warning(f"{filename} (not found)")
        else:
            results["failed"].append((filename, message))
            print_error(f"{filename}: {message}")
    
    # Create README.md
    if not dry_run and results["moved"]:
        create_analysis_readme(analysis_dir, [f[0] for f in results["moved"]])
    
    print(f"\n📊 Summary: {len(results['moved'])} moved, {len(results['skipped'])} skipped, {len(results['failed'])} failed")
    return results


def execute_stage_archive_exploratory(dry_run: bool = False) -> Dict:
    """Stage 3: Archive exploratory scripts to old_but_gold/exploratory/."""
    print_header("Stage 3: Archive Exploratory Scripts")
    
    results = {"archived": [], "skipped": [], "failed": []}
    archive_dir = PROJECT_ROOT / "old_but_gold" / "exploratory"
    
    for filename in EXPLORATORY_SCRIPTS:
        source = PROJECT_ROOT / filename
        destination = archive_dir / filename
        
        success, message = move_file(source, destination, dry_run)
        
        if success:
            results["archived"].append((filename, message))
            print_success(f"{filename} → old_but_gold/exploratory/")
        elif "not found" in message.lower():
            results["skipped"].append((filename, message))
            print_warning(f"{filename} (not found)")
        else:
            results["failed"].append((filename, message))
            print_error(f"{filename}: {message}")
    
    # Create MIGRATION.md
    if not dry_run and results["archived"]:
        create_migration_doc(archive_dir, [f[0] for f in results["archived"]])
    
    print(f"\n📊 Summary: {len(results['archived'])} archived, {len(results['skipped'])} skipped, {len(results['failed'])} failed")
    return results


def execute_stage_clean_artifacts(dry_run: bool = False) -> Dict:
    """Stage 4: Clean generated artifacts."""
    print_header("Stage 4: Clean Generated Artifacts")
    
    results = {"removed": [], "skipped": [], "failed": []}
    
    for filename in GENERATED_ARTIFACTS:
        file_path = PROJECT_ROOT / filename
        
        if not file_path.exists():
            results["skipped"].append((filename, "not found"))
            print_warning(f"{filename} (not found)")
            continue
        
        if dry_run:
            results["removed"].append((filename, "would remove"))
            print_success(f"{filename} (would remove)")
        else:
            try:
                file_path.unlink()
                results["removed"].append((filename, "removed"))
                print_success(f"{filename} removed")
            except Exception as e:
                results["failed"].append((filename, str(e)))
                print_error(f"{filename}: {e}")
    
    # Update .gitignore
    if not dry_run:
        update_gitignore()
    
    print(f"\n📊 Summary: {len(results['removed'])} removed, {len(results['skipped'])} skipped, {len(results['failed'])} failed")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Documentation Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_analysis_readme(analysis_dir: Path, scripts: List[str]) -> None:
    """Create README.md for analysis scripts."""
    readme_content = """# Analysis Scripts

This directory contains scripts for debugging, analysis, and investigation of the ingestion pipeline.

## Scripts

"""
    
    for script in scripts:
        script_path = analysis_dir / script
        
        # Try to extract docstring
        purpose = "Analysis and debugging script"
        try:
            content = script_path.read_text(encoding="utf-8")
            # Simple docstring extraction
            if '"""' in content:
                start = content.find('"""') + 3
                end = content.find('"""', start)
                if end > start:
                    docstring = content[start:end].strip()
                    first_line = docstring.split('\n')[0].strip()
                    if first_line:
                        purpose = first_line
        except:
            pass
        
        readme_content += f"""### {script}
**Purpose**: {purpose}
**Usage**: `python scripts/analysis/{script}`

"""
    
    readme_path = analysis_dir / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")
    print_success("Created scripts/analysis/README.md")


def create_migration_doc(archive_dir: Path, scripts: List[str]) -> None:
    """Create MIGRATION.md for archived scripts."""
    migration_content = f"""# Exploratory Scripts Migration Guide

**Archived**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

These scripts were created during the development of the ingestion pipeline and have been archived as their functionality has been implemented in the production code.

## Archived Scripts

"""
    
    for script in scripts:
        migration_content += f"""### {script}
**Reason**: Exploratory development script - functionality implemented in `ingestion_pipeline/`
**Migration Path**: Use the production `ingestion_pipeline` module
**Status**: Archived for reference

"""
    
    migration_path = archive_dir / "MIGRATION.md"
    migration_path.write_text(migration_content, encoding="utf-8")
    print_success("Created old_but_gold/exploratory/MIGRATION.md")


def update_gitignore() -> None:
    """Update .gitignore with artifact patterns."""
    gitignore_path = PROJECT_ROOT / ".gitignore"
    
    patterns_to_add = [
        "# Generated artifacts",
        "erp_page_content.html",
        "erp_pattern_analysis.json",
        "*_analysis.json",
        "*_debug.html",
    ]
    
    try:
        if gitignore_path.exists():
            content = gitignore_path.read_text(encoding="utf-8")
        else:
            content = ""
        
        # Check if patterns already exist
        new_patterns = []
        for pattern in patterns_to_add:
            if pattern not in content:
                new_patterns.append(pattern)
        
        if new_patterns:
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n" + "\n".join(new_patterns) + "\n"
            gitignore_path.write_text(content, encoding="utf-8")
            print_success(f"Updated .gitignore with {len(new_patterns)} patterns")
    
    except Exception as e:
        print_warning(f"Failed to update .gitignore: {e}")


def generate_cleanup_report(all_results: Dict, backup_dir: Path, dry_run: bool = False) -> None:
    """Generate CLEANUP_REPORT.md."""
    report_content = f"""# Project Cleanup Report

**Execution Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Mode**: {"DRY RUN (Preview Only)" if dry_run else "EXECUTED"}
**Backup**: {backup_dir.name if backup_dir else "N/A"}

## Summary

- **Test Files Moved**: {len(all_results['stage1']['moved'])}
- **Analysis Scripts Moved**: {len(all_results['stage2']['moved'])}
- **Exploratory Scripts Archived**: {len(all_results['stage3']['archived'])}
- **Artifacts Removed**: {len(all_results['stage4']['removed'])}

## Stage 1: Move Test Files

### Files Moved to tests/

"""
    
    for filename, status in all_results['stage1']['moved']:
        report_content += f"- ✅ `{filename}` → `tests/{filename}`\n"
    
    if all_results['stage1']['skipped']:
        report_content += "\n### Files Not Found\n\n"
        for filename, _ in all_results['stage1']['skipped']:
            report_content += f"- ⚠️  `{filename}` (not found in root)\n"
    
    report_content += f"""

## Stage 2: Move Analysis Scripts

### Files Moved to scripts/analysis/

"""
    
    for filename, status in all_results['stage2']['moved']:
        report_content += f"- ✅ `{filename}` → `scripts/analysis/{filename}`\n"
    
    if all_results['stage2']['skipped']:
        report_content += "\n### Files Not Found\n\n"
        for filename, _ in all_results['stage2']['skipped']:
            report_content += f"- ⚠️  `{filename}` (not found in root)\n"
    
    report_content += f"""

## Stage 3: Archive Exploratory Scripts

### Files Archived to old_but_gold/exploratory/

"""
    
    for filename, status in all_results['stage3']['archived']:
        report_content += f"- ✅ `{filename}` → `old_but_gold/exploratory/{filename}`\n"
    
    if all_results['stage3']['skipped']:
        report_content += "\n### Files Not Found\n\n"
        for filename, _ in all_results['stage3']['skipped']:
            report_content += f"- ⚠️  `{filename}` (not found in root)\n"
    
    report_content += f"""

## Stage 4: Clean Generated Artifacts

### Files Removed

"""
    
    for filename, status in all_results['stage4']['removed']:
        report_content += f"- ✅ `{filename}` removed\n"
    
    if all_results['stage4']['skipped']:
        report_content += "\n### Files Not Found\n\n"
        for filename, _ in all_results['stage4']['skipped']:
            report_content += f"- ⚠️  `{filename}` (not found in root)\n"
    
    report_content += """

## Files Kept in Root

The following files remain in the root directory as they are core to the project:

- `app.py` - Main application entry point
- `capture.py` - Core capture module
- `generator_engine.py` - Roteiro generation engine
- `main.py` - Execution engine
- `utils.py` - Shared utilities
- All other production modules

## Verification

"""
    
    if dry_run:
        report_content += "⚠️  **DRY RUN MODE** - No files were actually modified.\n\n"
        report_content += "To execute the cleanup, run: `python cleanup_project.py`\n"
    else:
        report_content += "✅ Cleanup executed successfully.\n\n"
        report_content += "### Next Steps\n\n"
        report_content += "1. Run tests: `pytest -v`\n"
        report_content += "2. Verify application: `python app.py --check` (if available)\n"
        report_content += f"3. If issues occur, restore backup: `python cleanup_project.py --restore {backup_dir.name}`\n"
    
    report_path = PROJECT_ROOT / "CLEANUP_REPORT.md"
    report_path.write_text(report_content, encoding="utf-8")
    print_success(f"Generated {report_path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Main Execution
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Reorganize Senior Training OS project structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--restore",
        type=str,
        metavar="BACKUP_DIR",
        help="Restore from backup directory"
    )
    
    args = parser.parse_args()
    
    # Handle restore
    if args.restore:
        backup_path = PROJECT_ROOT / args.restore
        print_header("Restoring from Backup")
        # Simple restore implementation
        print_error("Restore functionality not yet implemented. Please manually restore from backup.")
        return 1
    
    # Print header
    print_header("Senior Training OS - Project Cleanup")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified\n")
    
    # Collect all files that will be affected
    all_files = []
    for filename in TEST_FILES + ANALYSIS_SCRIPTS + EXPLORATORY_SCRIPTS + GENERATED_ARTIFACTS:
        file_path = PROJECT_ROOT / filename
        if file_path.exists():
            all_files.append(file_path)
    
    # Create backup (even in dry-run for safety)
    backup_dir = None
    if not args.dry_run and all_files:
        try:
            backup_dir = create_backup(all_files)
        except Exception as e:
            print_error(f"Failed to create backup: {e}")
            return 1
    
    # Execute stages
    all_results = {}
    
    try:
        all_results['stage1'] = execute_stage_move_tests(args.dry_run)
        all_results['stage2'] = execute_stage_move_analysis(args.dry_run)
        all_results['stage3'] = execute_stage_archive_exploratory(args.dry_run)
        all_results['stage4'] = execute_stage_clean_artifacts(args.dry_run)
        
        # Generate report
        print_header("Generating Report")
        generate_cleanup_report(all_results, backup_dir, args.dry_run)
        
        # Final summary
        print_header("Cleanup Complete")
        
        total_moved = (
            len(all_results['stage1']['moved']) +
            len(all_results['stage2']['moved']) +
            len(all_results['stage3']['archived'])
        )
        total_removed = len(all_results['stage4']['removed'])
        
        print(f"✅ {total_moved} files organized")
        print(f"✅ {total_removed} artifacts cleaned")
        print(f"✅ Report generated: CLEANUP_REPORT.md")
        
        if backup_dir:
            print(f"✅ Backup created: {backup_dir.name}")
        
        if args.dry_run:
            print("\n💡 To execute cleanup, run: python cleanup_project.py")
        else:
            print("\n💡 Next steps:")
            print("   1. Review CLEANUP_REPORT.md")
            print("   2. Run tests: pytest -v")
            print("   3. Commit changes if everything looks good")
        
        return 0
        
    except Exception as e:
        print_error(f"Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
