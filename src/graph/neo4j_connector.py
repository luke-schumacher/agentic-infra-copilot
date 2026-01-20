"""
Neo4j Database Connector

Purpose:
- Establishes connection to Neo4j Knowledge Graph database
- Handles authentication and session management
- Provides CRUD operations for graph nodes and relationships
- Ensures connection pooling and error handling

Configuration: Uses environment variables from .env file

Usage:
    connector = Neo4jConnector()
    results = connector.execute_query("MATCH (n) RETURN n LIMIT 10")
    connector.close()
"""

from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class Neo4jConnector:
    """Connector for Neo4j Knowledge Graph database."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize Neo4j connector.

        Args:
            uri: Neo4j database URI (defaults to env var NEO4J_URI)
            username: Database username (defaults to env var NEO4J_USERNAME)
            password: Database password (defaults to env var NEO4J_PASSWORD)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD")

        if not self.password:
            raise ValueError(
                "Neo4j password must be provided via NEO4J_PASSWORD env var or parameter"
            )

        self.driver = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Neo4j database.

        Returns:
            True if connection successful
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._connected = False
            raise

    def is_connected(self) -> bool:
        """Check if connected to Neo4j."""
        return self._connected and self.driver is not None

    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters (optional)

        Returns:
            List of result records as dictionaries
        """
        if not self.is_connected():
            self.connect()

        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                records = [record.data() for record in result]
                logger.debug(f"Query returned {len(records)} records")
                return records
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            raise

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a write query within a transaction.

        Args:
            query: Cypher write query
            parameters: Query parameters

        Returns:
            Query summary/result
        """
        if not self.is_connected():
            self.connect()

        def _write_tx(tx, cypher, params):
            result = tx.run(cypher, params or {})
            return result.consume()

        try:
            with self.driver.session() as session:
                summary = session.execute_write(_write_tx, query, parameters)
                return {
                    "nodes_created": summary.counters.nodes_created,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set,
                }
        except Exception as e:
            logger.error(f"Write query failed: {e}")
            raise

    def create_node(
        self,
        label: str,
        properties: Dict[str, Any],
        unique_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a node in the graph.

        Args:
            label: Node label (e.g., "Device", "Error", "Procedure")
            properties: Node properties
            unique_key: Property name to use for MERGE (upsert) behavior

        Returns:
            Node element ID if created, None on failure
        """
        if not self.is_connected():
            self.connect()

        try:
            if unique_key and unique_key in properties:
                # Use MERGE for idempotent creation
                query = f"""
                MERGE (n:{label} {{{unique_key}: $unique_value}})
                SET n += $properties
                RETURN elementId(n) as node_id
                """
                params = {
                    "unique_value": properties[unique_key],
                    "properties": properties
                }
            else:
                # Simple CREATE
                query = f"""
                CREATE (n:{label} $properties)
                RETURN elementId(n) as node_id
                """
                params = {"properties": properties}

            with self.driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                if record:
                    node_id = record["node_id"]
                    logger.debug(f"Created/merged {label} node: {node_id}")
                    return node_id
                return None

        except Exception as e:
            logger.error(f"Node creation failed: {e}")
            raise

    def create_relationship(
        self,
        from_label: str,
        from_key: str,
        from_value: Any,
        to_label: str,
        to_key: str,
        to_value: Any,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create a relationship between two nodes.

        Args:
            from_label: Source node label
            from_key: Property key to identify source node
            from_value: Property value to identify source node
            to_label: Target node label
            to_key: Property key to identify target node
            to_value: Property value to identify target node
            relationship_type: Type of relationship (e.g., "CAUSES", "RESOLVES")
            properties: Relationship properties (optional)

        Returns:
            Relationship element ID if created, None on failure
        """
        if not self.is_connected():
            self.connect()

        try:
            # Use MERGE to avoid duplicate relationships
            query = f"""
            MATCH (a:{from_label} {{{from_key}: $from_value}})
            MATCH (b:{to_label} {{{to_key}: $to_value}})
            MERGE (a)-[r:{relationship_type}]->(b)
            SET r += $properties
            RETURN elementId(r) as rel_id
            """

            params = {
                "from_value": from_value,
                "to_value": to_value,
                "properties": properties or {}
            }

            with self.driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                if record:
                    rel_id = record["rel_id"]
                    logger.debug(f"Created {relationship_type} relationship: {rel_id}")
                    return rel_id
                else:
                    logger.warning(
                        f"Could not create relationship: {from_label}({from_value}) "
                        f"-[{relationship_type}]-> {to_label}({to_value})"
                    )
                    return None

        except Exception as e:
            logger.error(f"Relationship creation failed: {e}")
            raise

    def delete_all(self):
        """Delete all nodes and relationships (use with caution!)."""
        logger.warning("Deleting all nodes and relationships from graph")
        return self.execute_write("MATCH (n) DETACH DELETE n")

    def get_node_count(self) -> int:
        """Get total number of nodes in the graph."""
        result = self.execute_query("MATCH (n) RETURN count(n) as count")
        return result[0]["count"] if result else 0

    def get_relationship_count(self) -> int:
        """Get total number of relationships in the graph."""
        result = self.execute_query("MATCH ()-[r]->() RETURN count(r) as count")
        return result[0]["count"] if result else 0

    def get_stats(self) -> Dict[str, int]:
        """Get graph statistics."""
        return {
            "nodes": self.get_node_count(),
            "relationships": self.get_relationship_count()
        }

    def __enter__(self):
        """Context manager entry."""
        if not self.is_connected():
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
