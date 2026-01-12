# app/services/neo4j_client.py
import os
from typing import Optional
from neo4j import GraphDatabase, Driver


_DRIVER: Optional[Driver] = None


def get_driver() -> Driver:
    """
    Singleton del driver de Neo4j.
    Env:
      - NEO4J_URI (p.ej. bolt://neo4j:7687)
      - NEO4J_USER
      - NEO4J_PASSWORD
    """
    global _DRIVER
    if _DRIVER is None:
        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "neo4j")
        _DRIVER = GraphDatabase.driver(uri, auth=(user, pwd))
    return _DRIVER


def close_driver() -> None:
    global _DRIVER
    if _DRIVER is not None:
        _DRIVER.close()
        _DRIVER = None
