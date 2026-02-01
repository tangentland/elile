# Task 11.12: Graph Visualization Core

## Overview

Implement a unified graph visualization system for screening data that supports multiple view modes, real-time updates, and CRUD operations for investigator review. This serves as the foundation for the Investigation Workbench, Security Console, and observability tooling.

**Priority**: P1 | **Effort**: 8 days | **Status**: Not Started

## Dependencies

- Task 10.3: Screening API Endpoints
- Task 10.4: Webhook System (for WebSocket infrastructure)
- Task 5.9: SAR Loop Orchestrator (for trace data)
- Task 6.6: Connection Analyzer (for entity network data)
- Task 7.5: Screening State Manager (for live status)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GRAPH VISUALIZATION SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         FRONTEND (React + TypeScript)                │    │
│  │                                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │    │
│  │  │ React Flow  │  │ Cytoscape.js│  │   Zustand   │  │  React    │  │    │
│  │  │ (Structured)│  │  (Organic)  │  │   (State)   │  │  Query    │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │    │
│  │                                                                      │    │
│  │  View Modes:                                                         │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │    │
│  │  │  Data    │ │Knowledge │ │  Entity  │ │  Trace   │               │    │
│  │  │ Sources  │ │  Graph   │ │ Network  │ │  View    │               │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                          WebSocket + REST API                                │
│                                    │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         BACKEND (FastAPI + PostgreSQL)               │    │
│  │                                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │    │
│  │  │   Graph     │  │   Graph     │  │  WebSocket  │  │  Apache   │  │    │
│  │  │    API      │  │   Service   │  │   Manager   │  │   AGE     │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Implementation Checklist

### Backend (Python/FastAPI)
- [ ] Install and configure Apache AGE extension
- [ ] Create graph schema migrations
- [ ] Implement GraphService with Cypher query support
- [ ] Build Graph REST API endpoints (CRUD)
- [ ] Implement WebSocket manager for live updates
- [ ] Create graph data transformers (screening → graph format)
- [ ] Add trace data collector and formatter
- [ ] Implement graph CRUD operations with audit logging
- [ ] Add filtering and search capabilities

### Frontend (React/TypeScript)
- [ ] Set up React + TypeScript + Vite project
- [ ] Install Cytoscape.js and React Flow
- [ ] Create unified graph data store (Zustand)
- [ ] Implement GraphViewer container component
- [ ] Build DataSourceView (React Flow)
- [ ] Build KnowledgeGraphView (Cytoscape.js)
- [ ] Build EntityNetworkView (Cytoscape.js)
- [ ] Build TraceView (React Flow)
- [ ] Implement node/edge detail panels
- [ ] Add CRUD controls for review mode
- [ ] Implement WebSocket client for live updates
- [ ] Add filtering and search UI
- [ ] Create layout controls

### Integration
- [ ] Connect frontend to backend APIs
- [ ] Test real-time updates
- [ ] Performance testing with large graphs
- [ ] Accessibility review

## Database Schema (Apache AGE)

```sql
-- migrations/versions/xxx_add_apache_age.py

-- Enable Apache AGE extension
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create graph for screening data
SELECT create_graph('screening_graph');

-- Create vertex labels (node types)
SELECT create_vlabel('screening_graph', 'Person');
SELECT create_vlabel('screening_graph', 'Organization');
SELECT create_vlabel('screening_graph', 'Location');
SELECT create_vlabel('screening_graph', 'Document');
SELECT create_vlabel('screening_graph', 'DataSource');
SELECT create_vlabel('screening_graph', 'Finding');
SELECT create_vlabel('screening_graph', 'Fact');
SELECT create_vlabel('screening_graph', 'Phase');
SELECT create_vlabel('screening_graph', 'ProviderCall');

-- Create edge labels (relationship types)
SELECT create_elabel('screening_graph', 'EMPLOYED_BY');
SELECT create_elabel('screening_graph', 'MANAGED_BY');
SELECT create_elabel('screening_graph', 'COLLEAGUE_OF');
SELECT create_elabel('screening_graph', 'FAMILY_MEMBER');
SELECT create_elabel('screening_graph', 'BUSINESS_PARTNER');
SELECT create_elabel('screening_graph', 'OWNS');
SELECT create_elabel('screening_graph', 'CONTROLS');
SELECT create_elabel('screening_graph', 'LOCATED_AT');
SELECT create_elabel('screening_graph', 'SOURCED_FROM');
SELECT create_elabel('screening_graph', 'ATTESTED_BY');
SELECT create_elabel('screening_graph', 'CORROBORATED_BY');
SELECT create_elabel('screening_graph', 'CONTRADICTS');
SELECT create_elabel('screening_graph', 'TRIGGERED');
SELECT create_elabel('screening_graph', 'PRODUCED');
SELECT create_elabel('screening_graph', 'DEPENDS_ON');

-- Index for fast lookups by screening_id
-- (Vertices store screening_id as a property)
CREATE INDEX idx_vertex_screening ON ag_catalog.screening_graph_vertices
USING gin ((properties -> 'screening_id'));
```

## Backend Implementation

### Graph Service

```python
# src/elile/graph/service.py
from uuid import UUID
from typing import AsyncGenerator
import asyncpg
from pydantic import BaseModel

from elile.graph.models import (
    GraphNode, GraphEdge, ScreeningGraph, GraphViewMode,
    NodeType, EdgeType, GraphUpdate
)
from elile.graph.cypher import CypherQueryBuilder
from elile.core.audit import AuditLogger


class GraphServiceConfig(BaseModel):
    """Configuration for graph service."""
    max_depth: int = 3
    max_nodes_per_query: int = 500
    enable_audit_logging: bool = True


class GraphService:
    """
    Service for managing screening graphs using Apache AGE.

    Provides:
    - Graph CRUD operations
    - Multi-view data transformation
    - Real-time update publishing
    - Audit logging for all mutations
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        config: GraphServiceConfig,
        audit_logger: AuditLogger,
        websocket_manager: WebSocketManager,
    ):
        self.db = db_pool
        self.config = config
        self.audit = audit_logger
        self.ws = websocket_manager
        self.cypher = CypherQueryBuilder()

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    async def get_screening_graph(
        self,
        screening_id: UUID,
        view_mode: GraphViewMode,
        depth: int = 2,
        filters: GraphFilters | None = None,
    ) -> ScreeningGraph:
        """
        Get graph representation of a screening.

        Args:
            screening_id: The screening to retrieve
            view_mode: Which view to render (data_sources, knowledge_graph, etc.)
            depth: How many hops to traverse (for entity network)
            filters: Optional filters to apply

        Returns:
            ScreeningGraph with nodes and edges for the requested view
        """
        match view_mode:
            case GraphViewMode.DATA_SOURCES:
                return await self._get_data_source_graph(screening_id, filters)
            case GraphViewMode.KNOWLEDGE_GRAPH:
                return await self._get_knowledge_graph(screening_id, filters)
            case GraphViewMode.ENTITY_NETWORK:
                return await self._get_entity_network(screening_id, depth, filters)
            case GraphViewMode.TRACE:
                return await self._get_trace_graph(screening_id, filters)

    async def _get_data_source_graph(
        self,
        screening_id: UUID,
        filters: GraphFilters | None,
    ) -> ScreeningGraph:
        """Get data source topology view."""

        query = """
        SELECT * FROM cypher('screening_graph', $$
            MATCH (ds:DataSource {screening_id: $screening_id})
            OPTIONAL MATCH (ds)-[r:PRODUCED]->(f:Fact)
            RETURN ds, collect(DISTINCT f) as facts, count(f) as fact_count
        $$, %s) AS (ds agtype, facts agtype, fact_count agtype);
        """

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, {'screening_id': str(screening_id)})

        nodes = []
        edges = []

        for row in rows:
            ds = self._parse_vertex(row['ds'])
            nodes.append(GraphNode(
                id=ds['id'],
                type=NodeType.DATA_SOURCE,
                label=ds['properties']['provider_name'],
                shape='rectangle',
                color=self._status_color(ds['properties'].get('status')),
                status=ds['properties'].get('status'),
                data={
                    'provider_id': ds['properties']['provider_id'],
                    'check_types': ds['properties'].get('check_types', []),
                    'latency_ms': ds['properties'].get('latency_ms'),
                    'cost': ds['properties'].get('cost'),
                },
                factCount=row['fact_count'],
            ))

            # Add edges to facts if showing details
            if filters and filters.include_facts:
                for fact in self._parse_vertices(row['facts']):
                    edges.append(GraphEdge(
                        id=f"{ds['id']}-{fact['id']}",
                        source=ds['id'],
                        target=fact['id'],
                        type=EdgeType.PRODUCED,
                        style='dotted',
                    ))

        return ScreeningGraph(
            screening_id=screening_id,
            view_mode=GraphViewMode.DATA_SOURCES,
            nodes=nodes,
            edges=edges,
            total_entities=0,
            total_facts=sum(n.factCount or 0 for n in nodes),
            total_relationships=len(edges),
            risk_connections=0,
            suggested_layout='dagre',
        )

    async def _get_knowledge_graph(
        self,
        screening_id: UUID,
        filters: GraphFilters | None,
    ) -> ScreeningGraph:
        """Get entity and fact knowledge graph."""

        # Get all entities and relationships for this screening
        query = """
        SELECT * FROM cypher('screening_graph', $$
            MATCH (e {screening_id: $screening_id})
            WHERE e:Person OR e:Organization OR e:Location OR e:Finding
            OPTIONAL MATCH (e)-[r]-(other {screening_id: $screening_id})
            RETURN e, collect(DISTINCT {rel: r, other: other}) as connections
        $$, %s) AS (entity agtype, connections agtype);
        """

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, {'screening_id': str(screening_id)})

        nodes = []
        edges = []
        seen_edges = set()

        for row in rows:
            entity = self._parse_vertex(row['entity'])
            node_type = NodeType(entity['label'].lower())

            nodes.append(GraphNode(
                id=entity['id'],
                type=node_type,
                label=entity['properties'].get('name', entity['properties'].get('label', 'Unknown')),
                shape=self._node_shape(node_type),
                color=self._risk_color(entity['properties'].get('risk_level')),
                risk_level=entity['properties'].get('risk_level'),
                confidence=entity['properties'].get('confidence'),
                flags=entity['properties'].get('flags', []),
                data=entity['properties'],
            ))

            # Process connections
            for conn in self._parse_connections(row['connections']):
                edge_id = self._edge_id(entity['id'], conn['other']['id'], conn['rel']['label'])
                if edge_id not in seen_edges:
                    seen_edges.add(edge_id)
                    edges.append(GraphEdge(
                        id=edge_id,
                        source=entity['id'],
                        target=conn['other']['id'],
                        type=EdgeType(conn['rel']['label'].lower()),
                        label=conn['rel']['label'].replace('_', ' ').title(),
                        confidence=conn['rel']['properties'].get('confidence'),
                        sources=conn['rel']['properties'].get('sources', []),
                    ))

        # Apply filters
        if filters:
            nodes, edges = self._apply_filters(nodes, edges, filters)

        return ScreeningGraph(
            screening_id=screening_id,
            view_mode=GraphViewMode.KNOWLEDGE_GRAPH,
            nodes=nodes,
            edges=edges,
            total_entities=len([n for n in nodes if n.type in (NodeType.PERSON, NodeType.ORGANIZATION)]),
            total_facts=len([n for n in nodes if n.type == NodeType.FINDING]),
            total_relationships=len(edges),
            risk_connections=len([e for e in edges if self._is_risk_edge(e)]),
            suggested_layout='force',
        )

    async def _get_entity_network(
        self,
        screening_id: UUID,
        depth: int,
        filters: GraphFilters | None,
    ) -> ScreeningGraph:
        """Get D2/D3 entity network view."""

        depth = min(depth, self.config.max_depth)

        # Find target entity and traverse relationships
        query = """
        SELECT * FROM cypher('screening_graph', $$
            MATCH (target:Person {screening_id: $screening_id, is_target: true})
            CALL {
                WITH target
                MATCH path = (target)-[*1..$depth]-(connected)
                WHERE connected:Person OR connected:Organization
                RETURN path, connected, length(path) as hops
            }
            RETURN target, collect(DISTINCT {path: path, entity: connected, hops: hops}) as network
        $$, %s) AS (target agtype, network agtype);
        """

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, {
                'screening_id': str(screening_id),
                'depth': depth,
            })

        # Process into nodes and edges with hop distance
        nodes, edges = self._process_network_paths(rows, depth)

        # Apply filters (risk only, PEP/sanctions, etc.)
        if filters:
            nodes, edges = self._apply_network_filters(nodes, edges, filters)

        return ScreeningGraph(
            screening_id=screening_id,
            view_mode=GraphViewMode.ENTITY_NETWORK,
            nodes=nodes,
            edges=edges,
            total_entities=len(nodes),
            total_facts=0,
            total_relationships=len(edges),
            risk_connections=len([n for n in nodes if n.risk_level in ('high', 'critical')]),
            suggested_layout='hierarchical',
        )

    async def _get_trace_graph(
        self,
        screening_id: UUID,
        filters: GraphFilters | None,
    ) -> ScreeningGraph:
        """Get SAR loop execution trace."""

        query = """
        SELECT * FROM cypher('screening_graph', $$
            MATCH (phase:Phase {screening_id: $screening_id})
            OPTIONAL MATCH (phase)-[t:TRIGGERED]->(call:ProviderCall)
            OPTIONAL MATCH (call)-[p:PRODUCED]->(result)
            RETURN phase,
                   collect(DISTINCT {call: call, trigger: t}) as calls,
                   collect(DISTINCT {result: result, produced: p}) as results
            ORDER BY phase.start_time
        $$, %s) AS (phase agtype, calls agtype, results agtype);
        """

        async with self.db.acquire() as conn:
            rows = await conn.fetch(query, {'screening_id': str(screening_id)})

        nodes, edges = self._process_trace_data(rows, filters)

        return ScreeningGraph(
            screening_id=screening_id,
            view_mode=GraphViewMode.TRACE,
            nodes=nodes,
            edges=edges,
            total_entities=0,
            total_facts=0,
            total_relationships=len(edges),
            risk_connections=0,
            suggested_layout='dagre',
            metadata={
                'total_duration_ms': self._calculate_total_duration(nodes),
                'api_calls': len([n for n in nodes if n.type == NodeType.PROVIDER_CALL]),
                'phases': len([n for n in nodes if n.type == NodeType.PHASE]),
            },
        )

    # =========================================================================
    # CRUD OPERATIONS (for Review Dashboard)
    # =========================================================================

    async def create_node(
        self,
        screening_id: UUID,
        node: GraphNodeCreate,
        actor_id: UUID,
    ) -> GraphNode:
        """Create a new node (manual entity addition during review)."""

        node_id = str(uuid7())

        query = f"""
        SELECT * FROM cypher('screening_graph', $$
            CREATE (n:{node.type.value} {{
                id: $id,
                screening_id: $screening_id,
                label: $label,
                created_by: $actor_id,
                created_at: datetime(),
                manual: true,
                properties: $properties
            }})
            RETURN n
        $$, %s) AS (n agtype);
        """

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(query, {
                'id': node_id,
                'screening_id': str(screening_id),
                'label': node.label,
                'actor_id': str(actor_id),
                'properties': node.data,
            })

        # Audit log
        await self.audit.log_event(
            event_type='graph_node_created',
            screening_id=screening_id,
            actor_id=actor_id,
            details={'node_id': node_id, 'node_type': node.type.value},
        )

        # Publish WebSocket update
        await self.ws.broadcast_to_screening(
            screening_id,
            GraphUpdate(type='node_added', node=self._row_to_node(row)),
        )

        return self._row_to_node(row)

    async def update_node(
        self,
        screening_id: UUID,
        node_id: str,
        update: GraphNodeUpdate,
        actor_id: UUID,
    ) -> GraphNode:
        """Update an existing node."""

        # Build dynamic SET clause
        set_clauses = []
        params = {'id': node_id, 'screening_id': str(screening_id)}

        if update.label is not None:
            set_clauses.append("n.label = $label")
            params['label'] = update.label

        if update.risk_level is not None:
            set_clauses.append("n.risk_level = $risk_level")
            params['risk_level'] = update.risk_level

        if update.flags is not None:
            set_clauses.append("n.flags = $flags")
            params['flags'] = update.flags

        if update.data is not None:
            for key, value in update.data.items():
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = value

        set_clauses.append("n.updated_by = $actor_id")
        set_clauses.append("n.updated_at = datetime()")
        params['actor_id'] = str(actor_id)

        query = f"""
        SELECT * FROM cypher('screening_graph', $$
            MATCH (n {{id: $id, screening_id: $screening_id}})
            SET {', '.join(set_clauses)}
            RETURN n
        $$, %s) AS (n agtype);
        """

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(query, params)

        if not row:
            raise NodeNotFoundError(node_id)

        # Audit log
        await self.audit.log_event(
            event_type='graph_node_updated',
            screening_id=screening_id,
            actor_id=actor_id,
            details={'node_id': node_id, 'updates': update.model_dump(exclude_none=True)},
        )

        # Publish WebSocket update
        node = self._row_to_node(row)
        await self.ws.broadcast_to_screening(
            screening_id,
            GraphUpdate(type='node_updated', node=node),
        )

        return node

    async def create_edge(
        self,
        screening_id: UUID,
        edge: GraphEdgeCreate,
        actor_id: UUID,
    ) -> GraphEdge:
        """Create a new edge (manual relationship during review)."""

        edge_id = str(uuid7())

        query = f"""
        SELECT * FROM cypher('screening_graph', $$
            MATCH (source {{id: $source_id, screening_id: $screening_id}})
            MATCH (target {{id: $target_id, screening_id: $screening_id}})
            CREATE (source)-[r:{edge.type.value} {{
                id: $id,
                created_by: $actor_id,
                created_at: datetime(),
                manual: true,
                confidence: $confidence,
                notes: $notes
            }}]->(target)
            RETURN source, r, target
        $$, %s) AS (source agtype, r agtype, target agtype);
        """

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(query, {
                'id': edge_id,
                'source_id': edge.source,
                'target_id': edge.target,
                'screening_id': str(screening_id),
                'actor_id': str(actor_id),
                'confidence': edge.confidence,
                'notes': edge.notes,
            })

        if not row:
            raise NodeNotFoundError(f"Source {edge.source} or target {edge.target}")

        # Audit log
        await self.audit.log_event(
            event_type='graph_edge_created',
            screening_id=screening_id,
            actor_id=actor_id,
            details={
                'edge_id': edge_id,
                'edge_type': edge.type.value,
                'source': edge.source,
                'target': edge.target,
            },
        )

        # Publish WebSocket update
        result_edge = self._row_to_edge(row)
        await self.ws.broadcast_to_screening(
            screening_id,
            GraphUpdate(type='edge_added', edge=result_edge),
        )

        return result_edge

    async def delete_edge(
        self,
        screening_id: UUID,
        edge_id: str,
        actor_id: UUID,
        reason: str,
    ) -> None:
        """Delete an edge (remove erroneous relationship)."""

        # First get the edge for audit
        query_get = """
        SELECT * FROM cypher('screening_graph', $$
            MATCH ()-[r {id: $edge_id}]-()
            RETURN r
        $$, %s) AS (r agtype);
        """

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(query_get, {'edge_id': edge_id})

            if not row:
                raise EdgeNotFoundError(edge_id)

            edge_data = self._parse_edge(row['r'])

            # Delete the edge
            query_delete = """
            SELECT * FROM cypher('screening_graph', $$
                MATCH ()-[r {id: $edge_id}]-()
                DELETE r
            $$, %s) AS (result agtype);
            """
            await conn.execute(query_delete, {'edge_id': edge_id})

        # Audit log
        await self.audit.log_event(
            event_type='graph_edge_deleted',
            screening_id=screening_id,
            actor_id=actor_id,
            details={
                'edge_id': edge_id,
                'edge_type': edge_data['label'],
                'reason': reason,
            },
        )

        # Publish WebSocket update
        await self.ws.broadcast_to_screening(
            screening_id,
            GraphUpdate(type='edge_deleted', edge_id=edge_id),
        )

    async def flag_node(
        self,
        screening_id: UUID,
        node_id: str,
        flag_type: FlagType,
        reason: str,
        actor_id: UUID,
    ) -> GraphNode:
        """Flag a node for attention during review."""

        return await self.update_node(
            screening_id=screening_id,
            node_id=node_id,
            update=GraphNodeUpdate(
                flags=[flag_type.value],
                data={'flag_reason': reason, 'flagged_by': str(actor_id)},
            ),
            actor_id=actor_id,
        )

    async def verify_edge(
        self,
        screening_id: UUID,
        edge_id: str,
        verified: bool,
        evidence: str | None,
        actor_id: UUID,
    ) -> GraphEdge:
        """Mark an edge as verified or disputed."""

        query = """
        SELECT * FROM cypher('screening_graph', $$
            MATCH ()-[r {id: $edge_id}]-()
            SET r.verified = $verified,
                r.verification_evidence = $evidence,
                r.verified_by = $actor_id,
                r.verified_at = datetime()
            RETURN r
        $$, %s) AS (r agtype);
        """

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(query, {
                'edge_id': edge_id,
                'verified': verified,
                'evidence': evidence,
                'actor_id': str(actor_id),
            })

        if not row:
            raise EdgeNotFoundError(edge_id)

        # Audit log
        await self.audit.log_event(
            event_type='graph_edge_verified',
            screening_id=screening_id,
            actor_id=actor_id,
            details={
                'edge_id': edge_id,
                'verified': verified,
                'evidence': evidence,
            },
        )

        edge = self._row_to_edge(row)
        await self.ws.broadcast_to_screening(
            screening_id,
            GraphUpdate(type='edge_updated', edge=edge),
        )

        return edge

    async def merge_entities(
        self,
        screening_id: UUID,
        source_ids: list[str],
        target_id: str,
        actor_id: UUID,
    ) -> GraphNode:
        """Merge duplicate entities into one."""

        # Move all relationships from sources to target
        query = """
        SELECT * FROM cypher('screening_graph', $$
            // Get target node
            MATCH (target {id: $target_id, screening_id: $screening_id})

            // For each source, move its relationships to target
            UNWIND $source_ids AS source_id
            MATCH (source {id: source_id})

            // Move outgoing relationships
            OPTIONAL MATCH (source)-[r_out]->(other)
            WHERE other.id <> $target_id
            CREATE (target)-[new_r_out:MERGED_FROM]->(other)
            SET new_r_out = properties(r_out)
            DELETE r_out

            // Move incoming relationships
            OPTIONAL MATCH (other)-[r_in]->(source)
            WHERE other.id <> $target_id
            CREATE (other)-[new_r_in:MERGED_FROM]->(target)
            SET new_r_in = properties(r_in)
            DELETE r_in

            // Mark source as merged
            SET source.merged_into = $target_id,
                source.merged_at = datetime(),
                source.merged_by = $actor_id

            RETURN target
        $$, %s) AS (target agtype);
        """

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(query, {
                'target_id': target_id,
                'source_ids': source_ids,
                'screening_id': str(screening_id),
                'actor_id': str(actor_id),
            })

        # Audit log
        await self.audit.log_event(
            event_type='graph_entities_merged',
            screening_id=screening_id,
            actor_id=actor_id,
            details={
                'source_ids': source_ids,
                'target_id': target_id,
            },
        )

        # Publish full graph refresh
        await self.ws.broadcast_to_screening(
            screening_id,
            GraphUpdate(type='graph_refresh'),
        )

        return self._row_to_node(row)

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _node_shape(self, node_type: NodeType) -> str:
        """Get shape for node type."""
        shapes = {
            NodeType.PERSON: 'circle',
            NodeType.ORGANIZATION: 'diamond',
            NodeType.LOCATION: 'square',
            NodeType.DOCUMENT: 'triangle',
            NodeType.DATA_SOURCE: 'rectangle',
            NodeType.FINDING: 'star',
            NodeType.FACT: 'ellipse',
            NodeType.PHASE: 'rectangle',
            NodeType.PROVIDER_CALL: 'rectangle',
        }
        return shapes.get(node_type, 'circle')

    def _status_color(self, status: str | None) -> str:
        """Get color for status."""
        colors = {
            'pending': '#9CA3AF',    # gray
            'running': '#3B82F6',    # blue
            'complete': '#10B981',   # green
            'failed': '#EF4444',     # red
        }
        return colors.get(status, '#9CA3AF')

    def _risk_color(self, risk_level: str | None) -> str:
        """Get color for risk level."""
        colors = {
            'low': '#10B981',        # green
            'moderate': '#F59E0B',   # amber
            'high': '#F97316',       # orange
            'critical': '#EF4444',   # red
        }
        return colors.get(risk_level, '#6B7280')  # gray default
```

### Graph API Endpoints

```python
# src/elile/api/routers/v1/graph.py
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from uuid import UUID

from elile.graph.service import GraphService
from elile.graph.models import (
    ScreeningGraph, GraphNode, GraphEdge, GraphViewMode,
    GraphNodeCreate, GraphNodeUpdate, GraphEdgeCreate,
    GraphFilters, FlagType,
)
from elile.api.dependencies import get_graph_service, get_current_user


router = APIRouter(prefix="/graph", tags=["graph"])


# =============================================================================
# READ ENDPOINTS
# =============================================================================

@router.get("/screenings/{screening_id}")
async def get_screening_graph(
    screening_id: UUID,
    view_mode: GraphViewMode = Query(default=GraphViewMode.KNOWLEDGE_GRAPH),
    depth: int = Query(default=2, ge=1, le=3),
    include_facts: bool = Query(default=False),
    risk_only: bool = Query(default=False),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    graph_service: GraphService = Depends(get_graph_service),
) -> ScreeningGraph:
    """
    Get graph representation of a screening.

    View modes:
    - **data_sources**: Provider topology with collection status
    - **knowledge_graph**: Facts and entities with relationships
    - **entity_network**: D2/D3 connection graph
    - **trace**: SAR loop execution trace
    """
    filters = GraphFilters(
        include_facts=include_facts,
        risk_only=risk_only,
        min_confidence=min_confidence,
    )

    return await graph_service.get_screening_graph(
        screening_id=screening_id,
        view_mode=view_mode,
        depth=depth,
        filters=filters,
    )


@router.get("/screenings/{screening_id}/nodes/{node_id}")
async def get_node_details(
    screening_id: UUID,
    node_id: str,
    include_connections: bool = Query(default=True),
    graph_service: GraphService = Depends(get_graph_service),
) -> NodeDetails:
    """Get detailed information about a specific node."""
    return await graph_service.get_node_details(
        screening_id=screening_id,
        node_id=node_id,
        include_connections=include_connections,
    )


@router.get("/screenings/{screening_id}/edges/{edge_id}")
async def get_edge_details(
    screening_id: UUID,
    edge_id: str,
    graph_service: GraphService = Depends(get_graph_service),
) -> EdgeDetails:
    """Get detailed information about a specific edge."""
    return await graph_service.get_edge_details(
        screening_id=screening_id,
        edge_id=edge_id,
    )


# =============================================================================
# CRUD ENDPOINTS (Review Dashboard)
# =============================================================================

@router.post("/screenings/{screening_id}/nodes")
async def create_node(
    screening_id: UUID,
    node: GraphNodeCreate,
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> GraphNode:
    """
    Create a new node manually during investigator review.

    Use cases:
    - Add entity discovered through manual research
    - Create placeholder for unresolved reference
    """
    return await graph_service.create_node(
        screening_id=screening_id,
        node=node,
        actor_id=current_user.id,
    )


@router.patch("/screenings/{screening_id}/nodes/{node_id}")
async def update_node(
    screening_id: UUID,
    node_id: str,
    update: GraphNodeUpdate,
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> GraphNode:
    """Update node properties during review."""
    return await graph_service.update_node(
        screening_id=screening_id,
        node_id=node_id,
        update=update,
        actor_id=current_user.id,
    )


@router.post("/screenings/{screening_id}/nodes/{node_id}/flag")
async def flag_node(
    screening_id: UUID,
    node_id: str,
    flag_type: FlagType,
    reason: str,
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> GraphNode:
    """Flag a node for attention."""
    return await graph_service.flag_node(
        screening_id=screening_id,
        node_id=node_id,
        flag_type=flag_type,
        reason=reason,
        actor_id=current_user.id,
    )


@router.post("/screenings/{screening_id}/edges")
async def create_edge(
    screening_id: UUID,
    edge: GraphEdgeCreate,
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> GraphEdge:
    """
    Create a new edge manually during investigator review.

    Use cases:
    - Establish relationship discovered through manual research
    - Connect entities from different sources
    """
    return await graph_service.create_edge(
        screening_id=screening_id,
        edge=edge,
        actor_id=current_user.id,
    )


@router.delete("/screenings/{screening_id}/edges/{edge_id}")
async def delete_edge(
    screening_id: UUID,
    edge_id: str,
    reason: str = Query(..., min_length=10),
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove an erroneous edge."""
    await graph_service.delete_edge(
        screening_id=screening_id,
        edge_id=edge_id,
        actor_id=current_user.id,
        reason=reason,
    )


@router.post("/screenings/{screening_id}/edges/{edge_id}/verify")
async def verify_edge(
    screening_id: UUID,
    edge_id: str,
    verified: bool,
    evidence: str | None = None,
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> GraphEdge:
    """Mark an edge as verified or disputed."""
    return await graph_service.verify_edge(
        screening_id=screening_id,
        edge_id=edge_id,
        verified=verified,
        evidence=evidence,
        actor_id=current_user.id,
    )


@router.post("/screenings/{screening_id}/nodes/merge")
async def merge_nodes(
    screening_id: UUID,
    source_ids: list[str],
    target_id: str,
    graph_service: GraphService = Depends(get_graph_service),
    current_user: User = Depends(get_current_user),
) -> GraphNode:
    """Merge duplicate entities into one."""
    return await graph_service.merge_entities(
        screening_id=screening_id,
        source_ids=source_ids,
        target_id=target_id,
        actor_id=current_user.id,
    )


# =============================================================================
# WEBSOCKET FOR LIVE UPDATES
# =============================================================================

@router.websocket("/screenings/{screening_id}/live")
async def screening_graph_websocket(
    websocket: WebSocket,
    screening_id: UUID,
    graph_service: GraphService = Depends(get_graph_service),
):
    """
    WebSocket for live graph updates during active screening.

    Events sent to client:
    - node_added: New entity discovered
    - node_updated: Status/risk change
    - edge_added: New relationship established
    - edge_updated: Relationship verified/disputed
    - edge_deleted: Relationship removed
    - fact_added: New fact collected
    - phase_changed: SAR phase transition
    - graph_refresh: Full refresh needed (after merge, etc.)
    """
    await websocket.accept()

    # Subscribe to screening updates
    await graph_service.ws.subscribe(websocket, screening_id)

    try:
        while True:
            # Keep connection alive, handle client messages if needed
            data = await websocket.receive_json()

            # Client can request specific views
            if data.get('type') == 'request_view':
                graph = await graph_service.get_screening_graph(
                    screening_id=screening_id,
                    view_mode=GraphViewMode(data.get('view_mode', 'knowledge_graph')),
                )
                await websocket.send_json({
                    'type': 'graph_data',
                    'data': graph.model_dump(),
                })

    except WebSocketDisconnect:
        await graph_service.ws.unsubscribe(websocket, screening_id)
```

## Frontend Implementation

### Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── graph/
│   │   │   ├── GraphViewer.tsx          # Main container
│   │   │   ├── DataSourceView.tsx       # React Flow view
│   │   │   ├── KnowledgeGraphView.tsx   # Cytoscape view
│   │   │   ├── EntityNetworkView.tsx    # Cytoscape view
│   │   │   ├── TraceView.tsx            # React Flow view
│   │   │   ├── NodeDetailPanel.tsx      # Detail sidebar
│   │   │   ├── EdgeDetailPanel.tsx      # Edge details
│   │   │   ├── GraphToolbar.tsx         # View controls
│   │   │   ├── GraphFilters.tsx         # Filter panel
│   │   │   └── GraphCRUDControls.tsx    # Review mode controls
│   │   └── ...
│   ├── hooks/
│   │   ├── useGraphData.ts              # React Query hook
│   │   ├── useGraphWebSocket.ts         # WebSocket hook
│   │   └── useGraphCRUD.ts              # Mutation hooks
│   ├── stores/
│   │   └── graphStore.ts                # Zustand store
│   ├── types/
│   │   └── graph.ts                     # TypeScript types
│   └── utils/
│       ├── graphLayouts.ts              # Layout algorithms
│       └── graphStyles.ts               # Node/edge styling
├── package.json
└── vite.config.ts
```

### Core Types

```typescript
// src/types/graph.ts

export type NodeType =
  | 'person'
  | 'organization'
  | 'location'
  | 'document'
  | 'data_source'
  | 'finding'
  | 'fact'
  | 'phase'
  | 'provider_call';

export type EdgeType =
  | 'employed_by'
  | 'managed_by'
  | 'colleague_of'
  | 'family_member'
  | 'business_partner'
  | 'owns'
  | 'controls'
  | 'located_at'
  | 'sourced_from'
  | 'attested_by'
  | 'corroborated_by'
  | 'contradicts'
  | 'triggered'
  | 'produced'
  | 'depends_on';

export type GraphViewMode =
  | 'data_sources'
  | 'knowledge_graph'
  | 'entity_network'
  | 'trace';

export type RiskLevel = 'low' | 'moderate' | 'high' | 'critical';

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  shape: string;
  color: string;
  size?: number;
  position?: { x: number; y: number };

  // Status (for data sources)
  status?: 'pending' | 'running' | 'complete' | 'failed';
  progress?: number;
  factCount?: number;
  latency?: number;

  // Risk (for entities)
  riskLevel?: RiskLevel;
  riskScore?: number;
  confidence?: number;
  flags?: string[];

  // Review state
  verified?: boolean;
  disputed?: boolean;
  manual?: boolean;

  // Arbitrary data
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  label?: string;
  style?: 'solid' | 'dashed' | 'dotted';
  color?: string;
  width?: number;
  animated?: boolean;

  confidence?: number;
  sources?: string[];

  verified?: boolean;
  disputed?: boolean;
  manual?: boolean;
  notes?: string;
}

export interface ScreeningGraph {
  screeningId: string;
  viewMode: GraphViewMode;
  nodes: GraphNode[];
  edges: GraphEdge[];

  totalEntities: number;
  totalFacts: number;
  totalRelationships: number;
  riskConnections: number;

  suggestedLayout: string;
  isLive: boolean;
  lastUpdated: string;
}

export interface GraphFilters {
  includeFacts?: boolean;
  riskOnly?: boolean;
  minConfidence?: number;
  nodeTypes?: NodeType[];
  edgeTypes?: EdgeType[];
  searchQuery?: string;
}

export type GraphUpdateType =
  | 'node_added'
  | 'node_updated'
  | 'edge_added'
  | 'edge_updated'
  | 'edge_deleted'
  | 'graph_refresh';

export interface GraphUpdate {
  type: GraphUpdateType;
  node?: GraphNode;
  edge?: GraphEdge;
  edgeId?: string;
}
```

### Main Graph Viewer Component

```tsx
// src/components/graph/GraphViewer.tsx
import React, { useState, useCallback } from 'react';
import { useGraphData, useGraphWebSocket } from '@/hooks';
import { useGraphStore } from '@/stores/graphStore';
import { DataSourceView } from './DataSourceView';
import { KnowledgeGraphView } from './KnowledgeGraphView';
import { EntityNetworkView } from './EntityNetworkView';
import { TraceView } from './TraceView';
import { NodeDetailPanel } from './NodeDetailPanel';
import { EdgeDetailPanel } from './EdgeDetailPanel';
import { GraphToolbar } from './GraphToolbar';
import { GraphFilters } from './GraphFilters';
import { GraphCRUDControls } from './GraphCRUDControls';
import type { GraphViewMode, GraphNode, GraphEdge, GraphFilters as Filters } from '@/types/graph';

interface GraphViewerProps {
  screeningId: string;
  initialView?: GraphViewMode;
  editable?: boolean;  // Enable CRUD for review mode
  isLive?: boolean;    // Enable WebSocket updates
}

export function GraphViewer({
  screeningId,
  initialView = 'knowledge_graph',
  editable = false,
  isLive = false,
}: GraphViewerProps) {
  const [viewMode, setViewMode] = useState<GraphViewMode>(initialView);
  const [filters, setFilters] = useState<Filters>({});
  const [depth, setDepth] = useState(2);

  // Zustand store for local graph state
  const {
    selectedNode,
    selectedEdge,
    setSelectedNode,
    setSelectedEdge,
    applyUpdate,
  } = useGraphStore();

  // Fetch graph data
  const { data: graph, isLoading, error } = useGraphData(
    screeningId,
    viewMode,
    depth,
    filters
  );

  // WebSocket for live updates
  useGraphWebSocket(screeningId, isLive, (update) => {
    applyUpdate(update);
  });

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    setSelectedEdge(null);
  }, []);

  const handleEdgeClick = useCallback((edge: GraphEdge) => {
    setSelectedEdge(edge);
    setSelectedNode(null);
  }, []);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
  }, []);

  if (isLoading) return <GraphSkeleton />;
  if (error) return <GraphError error={error} />;
  if (!graph) return null;

  return (
    <div className="flex h-full">
      {/* Main graph area */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <GraphToolbar
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          depth={depth}
          onDepthChange={setDepth}
          isLive={isLive}
          stats={{
            entities: graph.totalEntities,
            facts: graph.totalFacts,
            relationships: graph.totalRelationships,
            riskConnections: graph.riskConnections,
          }}
        />

        {/* Filters */}
        <GraphFilters
          filters={filters}
          onFiltersChange={setFilters}
          viewMode={viewMode}
        />

        {/* Graph visualization */}
        <div className="flex-1 relative">
          {viewMode === 'data_sources' && (
            <DataSourceView
              graph={graph}
              onNodeClick={handleNodeClick}
              onBackgroundClick={handleBackgroundClick}
            />
          )}

          {viewMode === 'knowledge_graph' && (
            <KnowledgeGraphView
              graph={graph}
              onNodeClick={handleNodeClick}
              onEdgeClick={handleEdgeClick}
              onBackgroundClick={handleBackgroundClick}
            />
          )}

          {viewMode === 'entity_network' && (
            <EntityNetworkView
              graph={graph}
              depth={depth}
              onNodeClick={handleNodeClick}
              onEdgeClick={handleEdgeClick}
              onBackgroundClick={handleBackgroundClick}
            />
          )}

          {viewMode === 'trace' && (
            <TraceView
              graph={graph}
              filters={filters}
              onNodeClick={handleNodeClick}
              onBackgroundClick={handleBackgroundClick}
            />
          )}

          {/* CRUD controls for review mode */}
          {editable && (
            <GraphCRUDControls
              screeningId={screeningId}
              selectedNode={selectedNode}
              selectedEdge={selectedEdge}
            />
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div className="w-80 border-l bg-gray-50">
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            screeningId={screeningId}
            editable={editable}
            onClose={() => setSelectedNode(null)}
          />
        )}

        {selectedEdge && (
          <EdgeDetailPanel
            edge={selectedEdge}
            screeningId={screeningId}
            editable={editable}
            onClose={() => setSelectedEdge(null)}
          />
        )}

        {!selectedNode && !selectedEdge && (
          <GraphSummaryPanel graph={graph} />
        )}
      </div>
    </div>
  );
}
```

### Cytoscape.js View (Knowledge Graph)

```tsx
// src/components/graph/KnowledgeGraphView.tsx
import React, { useEffect, useRef, useCallback } from 'react';
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import fcose from 'cytoscape-fcose';
import type { ScreeningGraph, GraphNode, GraphEdge } from '@/types/graph';
import { cytoscapeStyles, nodeShape, edgeStyle } from '@/utils/graphStyles';

// Register layouts
cytoscape.use(dagre);
cytoscape.use(fcose);

interface KnowledgeGraphViewProps {
  graph: ScreeningGraph;
  onNodeClick: (node: GraphNode) => void;
  onEdgeClick: (edge: GraphEdge) => void;
  onBackgroundClick: () => void;
}

export function KnowledgeGraphView({
  graph,
  onNodeClick,
  onEdgeClick,
  onBackgroundClick,
}: KnowledgeGraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: cytoscapeStyles,
      layout: { name: 'fcose', animate: true },
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;

    // Event handlers
    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data();
      onNodeClick(nodeData as GraphNode);
    });

    cy.on('tap', 'edge', (evt) => {
      const edgeData = evt.target.data();
      onEdgeClick(edgeData as GraphEdge);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onBackgroundClick();
      }
    });

    return () => {
      cy.destroy();
    };
  }, []);

  // Update graph data
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // Convert to Cytoscape format
    const elements = [
      // Nodes
      ...graph.nodes.map(node => ({
        group: 'nodes' as const,
        data: {
          ...node,
          // Cytoscape-specific
          shape: nodeShape(node.type),
          backgroundColor: node.color,
          label: node.label,
        },
      })),
      // Edges
      ...graph.edges.map(edge => ({
        group: 'edges' as const,
        data: {
          ...edge,
          // Cytoscape-specific
          lineStyle: edge.style || 'solid',
          lineColor: edge.color || '#666',
          label: edge.label,
        },
      })),
    ];

    // Batch update
    cy.batch(() => {
      cy.elements().remove();
      cy.add(elements);
    });

    // Run layout
    cy.layout({
      name: graph.suggestedLayout === 'force' ? 'fcose' : 'dagre',
      animate: true,
      animationDuration: 500,
    }).run();

  }, [graph]);

  // Highlight selected node
  const highlightNode = useCallback((nodeId: string | null) => {
    const cy = cyRef.current;
    if (!cy) return;

    // Reset all
    cy.elements().removeClass('highlighted dimmed');

    if (nodeId) {
      const node = cy.getElementById(nodeId);
      node.addClass('highlighted');

      // Highlight connected
      node.neighborhood().addClass('highlighted');

      // Dim others
      cy.elements().not(node.neighborhood().add(node)).addClass('dimmed');
    }
  }, []);

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      style={{ minHeight: '400px' }}
    />
  );
}
```

### React Flow View (Trace View)

```tsx
// src/components/graph/TraceView.tsx
import React, { useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';

import { PhaseNode } from './nodes/PhaseNode';
import { ProviderCallNode } from './nodes/ProviderCallNode';
import { DecisionNode } from './nodes/DecisionNode';
import type { ScreeningGraph, GraphNode, GraphFilters } from '@/types/graph';

const nodeTypes = {
  phase: PhaseNode,
  provider_call: ProviderCallNode,
  decision: DecisionNode,
};

interface TraceViewProps {
  graph: ScreeningGraph;
  filters: GraphFilters;
  onNodeClick: (node: GraphNode) => void;
  onBackgroundClick: () => void;
}

export function TraceView({
  graph,
  filters,
  onNodeClick,
  onBackgroundClick,
}: TraceViewProps) {
  // Apply trace-specific filters
  const filteredGraph = useMemo(() => {
    let nodes = graph.nodes;
    let edges = graph.edges;

    // Filter by granularity
    if (filters.traceGranularity === 'phases_only') {
      nodes = nodes.filter(n => n.type === 'phase');
      edges = edges.filter(e =>
        nodes.some(n => n.id === e.source) &&
        nodes.some(n => n.id === e.target)
      );
    } else if (filters.traceGranularity === 'errors_only') {
      nodes = nodes.filter(n => n.status === 'failed' || n.type === 'phase');
    } else if (filters.traceGranularity === 'slow_only') {
      nodes = nodes.filter(n =>
        n.type === 'phase' ||
        (n.latency && n.latency > 1000)
      );
    }

    return { ...graph, nodes, edges };
  }, [graph, filters]);

  // Convert to React Flow format with dagre layout
  const { nodes, edges } = useMemo(() => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 50 });

    // Add nodes to dagre
    filteredGraph.nodes.forEach(node => {
      dagreGraph.setNode(node.id, { width: 200, height: 60 });
    });

    // Add edges to dagre
    filteredGraph.edges.forEach(edge => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    // Calculate layout
    dagre.layout(dagreGraph);

    // Convert to React Flow nodes
    const rfNodes: Node[] = filteredGraph.nodes.map(node => {
      const { x, y } = dagreGraph.node(node.id);
      return {
        id: node.id,
        type: node.type,
        position: { x: x - 100, y: y - 30 },
        data: node,
      };
    });

    // Convert to React Flow edges
    const rfEdges: Edge[] = filteredGraph.edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      animated: edge.animated,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: edge.color || '#666' },
    }));

    return { nodes: rfNodes, edges: rfEdges };
  }, [filteredGraph]);

  const [rfNodes, setNodes, onNodesChange] = useNodesState(nodes);
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState(edges);

  // Update when graph changes
  React.useEffect(() => {
    setNodes(nodes);
    setEdges(edges);
  }, [nodes, edges]);

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    onNodeClick(node.data as GraphNode);
  }, [onNodeClick]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      onPaneClick={onBackgroundClick}
      nodeTypes={nodeTypes}
      fitView
      minZoom={0.2}
      maxZoom={2}
    >
      <Controls />
      <Background />
    </ReactFlow>
  );
}
```

## Testing Requirements

### Backend Tests
- Apache AGE query correctness
- Graph CRUD operations with audit logging
- WebSocket message delivery
- Filter application
- Layout hints generation

### Frontend Tests
- Component rendering for each view mode
- Node/edge click handling
- WebSocket update application
- Filter UI interactions
- CRUD control visibility based on permissions

### Integration Tests
- End-to-end graph loading
- Real-time updates via WebSocket
- CRUD operations with persistence
- Large graph performance (500+ nodes)

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] Apache AGE extension installed and configured
- [ ] Graph schema migrations created
- [ ] All four view modes implemented (data sources, knowledge graph, entity network, trace)
- [ ] CRUD operations working with audit logging
- [ ] WebSocket live updates functional
- [ ] Filters working (risk only, confidence threshold, node types)
- [ ] Detail panels showing node/edge information
- [ ] Performance acceptable with 500+ nodes
- [ ] Accessible (keyboard navigation, screen reader support)
- [ ] Tests passing with 85%+ coverage

## Deliverables

### Backend
- `src/elile/graph/__init__.py`
- `src/elile/graph/models.py`
- `src/elile/graph/service.py`
- `src/elile/graph/cypher.py`
- `src/elile/graph/websocket.py`
- `src/elile/api/routers/v1/graph.py`
- `migrations/versions/xxx_add_apache_age.py`
- `tests/unit/test_graph_service.py`
- `tests/integration/test_graph_api.py`

### Frontend
- `frontend/src/components/graph/*.tsx`
- `frontend/src/hooks/useGraph*.ts`
- `frontend/src/stores/graphStore.ts`
- `frontend/src/types/graph.ts`
- `frontend/src/utils/graphStyles.ts`
- `frontend/src/utils/graphLayouts.ts`
- `frontend/tests/components/graph/*.test.tsx`

## References

- Apache AGE: https://age.apache.org/
- Cytoscape.js: https://js.cytoscape.org/
- React Flow: https://reactflow.dev/
- Architecture: [11-interfaces.md](../architecture/11-interfaces.md)
- Trace Data: Task 5.9 (SAR Orchestrator)
- Entity Network: Task 6.6 (Connection Analyzer)

---

*Task Owner: [TBD]* | *Created: 2026-02-01*
