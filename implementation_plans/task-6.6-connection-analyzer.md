# Task 6.6: Connection Analyzer - Implementation Plan

## Overview

The Connection Analyzer maps relationships between entities, analyzes network graphs, and assesses risk propagation through connections for D2/D3 investigations. It builds on the Network Phase Handler (Task 5.14) to provide risk analysis of the discovered entity network.

## Requirements

### Functional Requirements
1. Build connection graphs from discovered entities and relations
2. Calculate risk propagation through network edges
3. Support D2 (direct) and D3 (extended) network analysis
4. Identify risky connections (sanctions, PEP, shell companies)
5. Generate visualization data for graph rendering
6. Calculate network centrality metrics

### Non-Functional Requirements
- Integration with NetworkProfile from investigation phase
- Configurable risk thresholds and decay factors
- Support for large networks (100 D2 + 500 D3 entities)

## Files Created/Modified

### New Files
- `src/elile/risk/connection_analyzer.py` - Main implementation (1224 lines)
- `tests/unit/test_connection_analyzer.py` - Unit tests (955 lines)

### Modified Files
- `src/elile/risk/__init__.py` - Added exports for new classes
- `CODEBASE_INDEX.md` - Added documentation for Pattern Recognizer and Connection Analyzer
- `IMPLEMENTATION_STATUS.md` - Updated phase status and task completion

## Key Patterns Used

### Graph Building
```python
# Build from entities and relations
graph = self._build_graph(
    subject_entity=subject,
    discovered_entities=entities,
    relations=relations,
    degree=SearchDegree.D2,
)
```

### Risk Propagation
Risk propagates through the network with decay factors:
- CRITICAL: 70% retained per hop
- HIGH: 60% retained per hop
- MODERATE: 50% retained per hop
- LOW: 30% retained per hop

Edge risk factors based on:
- Relation type (OWNERSHIP=1.0, SOCIAL=0.3)
- Connection strength (DIRECT=1.0, WEAK=0.4)
- Current vs past relationship

### Centrality Metrics
- Degree centrality: connections / max possible
- Betweenness centrality: frequency on shortest paths

## Classes and Data Structures

### Main Classes
| Class | Purpose |
|-------|---------|
| `ConnectionAnalyzer` | Analyzes network risk and builds graphs |
| `ConnectionGraph` | Graph structure with nodes, edges, metrics |
| `ConnectionNode` | Entity node with risk attributes |
| `ConnectionEdge` | Relationship edge with risk factor |
| `RiskPropagationPath` | Path through which risk reaches subject |
| `ConnectionAnalysisResult` | Complete analysis result |
| `AnalyzerConfig` | Configuration options |

### Enums
| Enum | Values |
|------|--------|
| `ConnectionRiskType` | 14 types: sanctions, PEP, shell_company, etc. |

### Constants
| Constant | Purpose |
|----------|---------|
| `RISK_DECAY_PER_HOP` | Risk retention by severity |
| `STRENGTH_MULTIPLIER` | Connection strength factors |
| `RELATION_RISK_FACTOR` | Relation type risk weights |

## Test Results

```
======================== 50 passed, 2 warnings in 0.84s ========================
```

### Test Categories
- Constants tests (3)
- Model tests (ConnectionNode, ConnectionEdge, ConnectionGraph, etc.) (11)
- Config tests (3)
- Basic operations tests (3)
- Graph building tests (5)
- Risk analysis tests (4)
- Risk propagation tests (4)
- Centrality metrics tests (2)
- NetworkProfile integration tests (1)
- Visualization data tests (3)
- Recommendations tests (3)
- Edge cases tests (5)
- Summary generation tests (3)

## Integration Points

### Dependencies
- `elile.agent.state.SearchDegree` - D1/D2/D3 degree enum
- `elile.investigation.phases.network` - DiscoveredEntity, EntityRelation, NetworkProfile, RiskLevel, etc.
- `elile.core.logging` - Structured logging

### Used By (Future)
- Task 6.7: Risk Aggregator - Will use connection analysis results
- Task 7.x: Screening Service - Will call analyzer for network risk
- Report generation - Will include connection risk in reports

## Acceptance Criteria

- [x] ConnectionAnalyzer builds graphs from entities and relations
- [x] Risk propagation calculated with configurable decay
- [x] D2 and D3 analysis supported
- [x] Centrality metrics calculated
- [x] Risk connections identified (sanctions, PEP, etc.)
- [x] Visualization data generated for graph rendering
- [x] NetworkProfile integration works
- [x] All 50 unit tests passing
- [x] Linting passes (ruff check)
- [x] Documentation updated

## Notes

1. The `network_profile` parameter in `_build_graph` is reserved for future enhancement where additional context from the profile could influence graph construction.

2. The graph parameter in `_format_propagation_description` and `_sum_propagated_risk` is passed for potential future use in generating more detailed descriptions.

3. Risk propagation uses a "diminishing returns" formula: `1 - product(1 - risk_i)` rather than simple addition to prevent risk scores from exceeding 1.0.
