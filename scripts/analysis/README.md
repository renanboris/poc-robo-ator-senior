# Analysis Scripts

This directory contains scripts for debugging, analysis, and investigation of the ingestion pipeline.

## Scripts

### analyze_erp_patterns.py
**Purpose**: Análise dos padrões de URL do ERP baseado no mapeamento manual do usuário.
**Usage**: `python scripts/analysis/analyze_erp_patterns.py`

### analyze_sitemap_structure.py
**Purpose**: Analyze sitemap structure to understand what was actually captured.
**Usage**: `python scripts/analysis/analyze_sitemap_structure.py`

### check_sitemap_content.py
**Purpose**: Check if sitemap contains .htm files inside important directories.
**Usage**: `python scripts/analysis/check_sitemap_content.py`

### debug_crawler.py
**Purpose**: Debug why crawler only found 126 URLs when sitemap has 710.
**Usage**: `python scripts/analysis/debug_crawler.py`

### debug_erp_discovery.py
**Purpose**: Debug da descoberta de URLs do ERP.
**Usage**: `python scripts/analysis/debug_erp_discovery.py`

