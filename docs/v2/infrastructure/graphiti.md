# Infrastructure — Graphiti + Memory Backends

## Overview

Graphiti is the preferred temporal-memory backend for V2. It is typically paired with FalkorDB for local use. The codebase still retains a Zep compatibility path for deployments that explicitly configure it.

## Current Memory Strategy

Preferred:

- Graphiti + FalkorDB

Compatibility fallback:

- Zep, when configured and selected through memory-backend settings

This means the product no longer depends on Zep for the normal V2 flow, but the compatibility code is still present.

## What Memory Is Used For

- storing simulation episodes / agent memory
- retrieving context for report/chat prompts
- preserving temporal context across discussions

## Current Code-Level Reality

- `GraphitiService` is provider-aware
- `MemoryService` decides whether Graphiti or Zep can serve a query
- report/chat code still exposes some `zep_context_used` compatibility fields in payloads

## Operational Notes

- Graphiti availability depends on the required Python packages plus a reachable graph store
- if Graphiti is unavailable and Zep is not configured, memory-backed search should degrade transparently or return a clear runtime error

## Validation

When changing memory plumbing, verify:

- Graphiti initialization works
- memory search returns context for a live session
- compatibility fallback behavior is still explicit and not silent
