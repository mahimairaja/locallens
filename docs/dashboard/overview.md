# Dashboard Overview

The web dashboard provides a visual interface for LocalLens with these pages:

## Dashboard

The main landing page showing index statistics: total files, total chunks, file type breakdown, and storage usage.

## Index

Upload or point to a folder for indexing. Shows progress with real-time updates via WebSocket. Displays results when complete.

## Search

Search your indexed files with a text input. Results show file name, relevance score, and a preview of the matching chunk. Supports filtering by file type.

## Ask

Ask natural language questions about your files. Answers stream token-by-token with source citations shown below. Includes a mic button for voice input and a speaker button for TTS playback on each answer.

## Voice

Voice features are integrated into the Ask page. Click the mic button to speak your question (requires Moonshine STT), and click the speaker icon on any answer to hear it read aloud (requires Piper TTS).
