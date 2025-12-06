# Code Review Style Guide for Fast Light Chat

## Project Overview
This is a high-performance real-time chat platform. The primary goal is achieving sub-150ms response times for all API/WebSocket communications.

## Review Priorities

### 1. Performance (Highest Priority)
- Flag any synchronous I/O operations
- Check for N+1 query patterns
- Verify proper use of connection pooling
- Ensure Redis caching is used for frequently accessed data
- Watch for unnecessary database hits

### 2. Security
- Verify input validation on all user inputs
- Check for SQL injection vulnerabilities
- Ensure sensitive data (passwords, tokens) are never logged or exposed
- Verify proper authentication checks

### 3. Code Quality
- Follow PEP 8 style guidelines
- Use Python 3.13+ type hints (`list[str]` not `List[str]`)
- Prefer async/await for all I/O operations
- Keep functions small and focused

### 4. FastAPI Best Practices
- Use Pydantic models for request/response validation
- Use dependency injection for database sessions and auth
- Return proper HTTP status codes
- Document endpoints with OpenAPI descriptions

## Language
Please provide code review comments in Korean (한국어).

## What to Ignore
- Markdown files
- Lock files (uv.lock, package-lock.json)
- Frontend code (frontend/)
- Test files (tests/)
