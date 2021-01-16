# Storing Structured Data

## STORY PLOT
- Story intro
- ** ART **

## Definitions
- Structured data
- Redis Hashes
- RedisJSON

### Structured Data

- Dictionaries
- Like SQL tables
- Objects
- May be nested
- ** STORY / ART **

### Redis Hashes

- What they are
- No nesting

### RedisJSON

- What it is
- Nesting
- ** STORY / ART **

## Example: People and Vehicles in a Spaceship

- ** STORY / ART **
- A deck that contains a Vehicle that contains a Person
- Explain the data model
- We're going to see how this works with Hashes and then RedisJSON

## Hash Implementation

- (Intro) With Redis Hashes: serialize to multiple hashes and sets
- Code walk-through
- Ups: No module; integrates well with RediSearch
- Downside: serialized nested structures

## RedisJSON Implementation

- (Intro) With RedisJSON: single document with nested objects
- Code walk-through
- Upside: Nested structures work well
- Downside: Doesn't work yet with RediSearch
