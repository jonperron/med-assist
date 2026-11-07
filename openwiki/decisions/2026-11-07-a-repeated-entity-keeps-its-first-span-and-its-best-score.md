---
type: decision
title: 2026-11-07 - A repeated entity keeps its first span and its best score
description: Deduplication in the entity extractor no longer discards a later, more confident mention; the first occurrence keeps its offsets and takes the highest score seen.
tags: [extraction, summarizer]
---

# 2026-11-07 - A repeated entity keeps its first span and its best score

## The problem this is answering

The extractor deduplicated by lower-cased text and label and kept the first
occurrence whole. A first mention scored 0.4 and a later one 0.9 therefore left
the summary, because the summary drops anything under `MIN_CONFIDENCE`.

## What was decided

The first occurrence keeps its text and offsets and takes the highest score
seen. Scores are compared after rounding, so a near-tie keeps the first.

## The alternative that was rejected

Replacing the entity wholesale with the best-scoring occurrence. It moves
`start` and `end` to a later mention, and the summarizer pairs examinations with
values by offset, so a value could be paired with a different test than before.
Its docstring also promises the first occurrence's offsets.

## What the choice costs

The kept span carries a score that belongs to a different mention. That is
fine for the confidence floor, which is the only use of the score, but the
score no longer describes the text at those offsets. A span first seen low and
seen high later now appears in summaries where it did not.
