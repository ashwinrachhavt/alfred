"""Pipeline node functions -- one per processing stage."""

from alfred.pipeline.nodes.chunk import chunk
from alfred.pipeline.nodes.classify import classify
from alfred.pipeline.nodes.embed import embed
from alfred.pipeline.nodes.extract import extract
from alfred.pipeline.nodes.load_document import load_document
from alfred.pipeline.nodes.persist import persist

__all__ = ["chunk", "classify", "embed", "extract", "load_document", "persist"]
