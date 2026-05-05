# AURA Smart Navigation Fallback

## Overview

The AURA Smart Navigation Fallback feature enhances AURA's ability to guide users to UI elements that are not currently visible in the DOM. When a user asks how to access a feature that requires navigation through nested menus or collapsed sections, AURA provides step-by-step guided navigation instead of generic responses.

## Features

- **Intelligent Element Detection**: Automatically detects when requested elements are not visible in the current DOM
- **Roteiro-Based Navigation**: Leverages saved roteiros to extract hierarchical navigation paths
- **Conversational Offers**: Presents navigation options in natural language (e.g., "Ele fica dentro do Senior Flow > SIGN, quer que eu te guie para lá?")
- **Step-by-Step Guidance**: Executes navigation sequences with visual highlights at each step
- **Performance Optimized**: 
  - Element visibility check: < 500ms
  - Index lookup: < 200ms for 95% of queries
  - Navigation step timeout: 2 seconds
- **Automatic Index Updates**: Watches roteiro directory for changes and updates index automatically
- **Metrics & Monitoring**: Tracks fallback activations, success rates, and performance

## Architecture

### Components

1. **NavigationFallbackEngine**: Main orchestrator that coordinates the fallback strategy
2. **RoteiroIndexer**: Fast O(log n) lookup with SQLite FTS5 and LRU cache
3. **NavigationPathExtractor**: Parses roteiro JSON files to extract navigation sequences
4. **GuidedNavigationExecutor**: Executes step-by-step navigation with visual feedback
5. **NavigationHighlighter** (Extension): Provides visual highlights and tooltips in the browser

### Data Flow

```
User Query → Element Visibility Check → Navigation Fallback Engine
                                              ↓
                                        Roteiro Index Search
                                              ↓
                                    Format Conversational Offer
                                              ↓
                                        User Confirmation
                                              ↓
                                    Execute Guided Navigation
                                              ↓
                                    Visual Highlights (Extension)
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Add the following to your `.env` file:

```env
# Enable/disable navigation fallback feature
NAVIGATION_FALLBACK_ENABLED=True

# Path to the navigation index SQLite database
ROTEIRO_INDEX_DB=roteiro_index.db

# LRU cache size for frequently accessed navigation paths
ROTEIRO_INDEX_CACHE_SIZE=100

# Timeout for navigation step execution (milliseconds)
NAVIGATION_STEP_TIMEOUT_MS=2000

# Timeout for element visibility check (milliseconds)
ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS=500
```

### 3. Run Database Migration

```bash
python migrate_navigation_index.py
```

To rebuild the index from scratch:

```bash
python migrate_navigation_index.py --rebuild
```

### 4. Start the Application

The navigation fallback engine will initialize automatically on app startup:

```bash
uvicorn app:app --reload
```

## Usage

### For End Users

1. **Ask AURA about a hidden feature**:
   - User: "Como faço para cancelar envelopes no SIGN?"
   - AURA: "Ele fica dentro do Senior Flow > SIGN > Nova Gestão, quer que eu te guie para lá?"

2. **Confirm guided navigation**:
   - User: "Sim, me guie"
   - AURA executes step-by-step navigation with visual highlights

3. **Decline guided navigation**:
   - User: "Não, obrigado"
   - AURA continues normal conversation

### For Developers

#### Check Navigation Metrics

```bash
curl http://localhost:8000/api/navigation/metrics
```

Response:
```json
{
  "fallback_activations": 42,
  "navigation_successes": 38,
  "navigation_failures": 4,
  "success_rate": 0.9048,
  "average_navigation_time_ms": 1250.5,
  "cache_hit_rate": 0.85,
  "cache_hits": 120,
  "cache_misses": 21,
  "index_size": 156
}
```

#### Rebuild Index Programmatically

```python
from navigation_fallback import RoteiroIndexer

indexer = RoteiroIndexer()
result = indexer.build_index()
print(f"Indexed {result['indexed_count']} roteiros in {result['duration_ms']}ms")
```

#### Search for Navigation Paths

```python
from navigation_fallback import get_navigation_fallback_engine

engine = get_navigation_fallback_engine()
result = await engine.handle_invisible_element(
    user_query="cancelar envelopes",
    dom_context="<current DOM>",
    tenant_id="senior_default"
)

if result["fallback_type"] == "navigation":
    print(f"Found path: {result['navigation_path']}")
```

## Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| Element visibility check | < 500ms | ✓ |
| Index lookup | < 200ms (95%) | ✓ |
| Navigation step timeout | 2 seconds | ✓ |
| Index build (1000 roteiros) | < 5 seconds | ✓ |
| Cache hit rate | > 80% | ✓ |

## Monitoring

### Structured Logging

All navigation events are logged in structured JSON format:

```json
{
  "event_type": "fallback_activation",
  "tenant_id": "senior_default",
  "user_query": "cancelar envelopes",
  "timestamp": 1704067200.0
}
```

Event types:
- `fallback_activation`: Fallback strategy activated
- `path_found`: Navigation path found in index
- `no_path_found`: No navigation path found
- `navigation_success`: Guided navigation completed successfully
- `navigation_failure`: Guided navigation failed
- `navigation_error`: Error during navigation execution

### Metrics Dashboard

Access metrics at: `http://localhost:8000/api/navigation/metrics`

## Troubleshooting

### Index Not Building

**Problem**: Migration script fails with "No roteiro files found"

**Solution**: Ensure `roteiros_salvos/` directory exists and contains `.json` files

### Element Not Found During Navigation

**Problem**: Navigation fails with "Element not found in DOM"

**Solution**: 
1. Check if the roteiro is up-to-date with current UI
2. Verify selector hints in roteiro JSON
3. Check if element requires authentication or specific permissions

### Low Cache Hit Rate

**Problem**: Cache hit rate < 50%

**Solution**:
1. Increase `ROTEIRO_INDEX_CACHE_SIZE` in `.env`
2. Check if queries are being normalized correctly
3. Review query patterns in logs

### File Watcher Not Working

**Problem**: Index not updating when roteiros change

**Solution**:
1. Verify `watchdog` is installed: `pip install watchdog`
2. Check logs for file watcher errors
3. Restart application to reinitialize watcher

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run navigation fallback tests only
pytest tests/ -k navigation

# Run with coverage
pytest tests/ --cov=navigation_fallback
```

### Adding New Navigation Patterns

1. Create or update roteiro JSON with navigation steps
2. Ensure `tipo_passo` is set to `"navigation"` for navigation steps
3. Include `pedagogia.tooltip_dap` with breadcrumb path
4. Index will update automatically via file watcher

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger("navigation_fallback").setLevel(logging.DEBUG)
```

## Limitations

1. **UI Structure Changes**: Navigation may fail if UI structure has changed since roteiro was created
2. **Dynamic Content**: Elements loaded asynchronously may not be detected immediately
3. **Iframe Content**: Navigation within iframes requires special handling
4. **Authentication**: Navigation assumes user is already authenticated

## Future Enhancements

1. **Machine Learning Path Ranking**: Train model to rank paths based on user success rates
2. **Adaptive Navigation**: Learn from failed navigations to update roteiro index
3. **Multi-Language Support**: Support navigation in multiple languages
4. **Voice-Guided Navigation**: Add audio narration for each step
5. **Navigation Recording**: Allow users to record new navigation paths

## Support

For issues or questions:
1. Check logs in `app.log`
2. Review structured navigation events
3. Check metrics at `/api/navigation/metrics`
4. Consult spec documentation in `.kiro/specs/aura-smart-navigation-fallback/`

## License

Part of Senior Training OS - Internal Use Only
