from langchain_core.prompts import ChatPromptTemplate


ROUTING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert in resistance training and exercise science.

Your task is to route a book chapter into exactly ONE collection based on its PRIMARY objective.

Available collections:

- principles
  Universal training concepts that apply regardless of the trainee's goal.

  Examples:
  - recovery science
  - progressive overload
  - periodization
  - rep range research
  - deload protocols
  - injury prevention

- hypertrophy
  Chapters primarily focused on maximizing skeletal muscle growth.

- strength
  Chapters primarily focused on maximizing force production and strength performance.

Routing rules:

1. Classify according to the chapter's PRIMARY objective, not every topic it mentions.

2. Ignore supporting material. Chapters about hypertrophy or strength often discuss recovery, anatomy, physiology, biomechanics, fatigue, and other general concepts to explain their main subject.

3. Choose "principles" ONLY when the chapter's main purpose is teaching concepts that are generally applicable across multiple training goals.

4. If the chapter's primary goal is muscle growth, choose "hypertrophy".

5. If the chapter's primary goal is strength development, choose "strength".

Return ONLY valid JSON matching this schema:

{{
    "collection": "principles | hypertrophy | strength"
}}
            """,
        ),
        (
            "human",
            "{chapter}",
        ),
    ]
)


PRINCIPLES_METADATA_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert in exercise science.

Your task is to extract structured metadata for a text chunk from the "principles" knowledge namespace.

Guidelines:

1. Read the chunk carefully and identify its PRIMARY concepts.

2. Every selected value must be explicitly supported by the chunk.

3. Never select a label simply because it is related to the topic or because the field cannot be empty.

4. Choose only labels that represent major concepts of the chunk, not passing mentions or examples.

5. Multiple values are allowed only when they are equally central to the chunk.

6. Prefer precision over completeness. It is better to return fewer correct labels than many weakly supported ones.

7. Use only the provided schema and return only the structured output.
            """,
        ),
        (
            "human",
            """
Book:
{book}

Chapter:
{chapter}

Chunk:
{text}
            """,
        ),
    ]
)


GOAL_METADATA_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert in exercise science.

Your task is to extract structured metadata for a text chunk from a goal-specific knowledge namespace.

Guidelines:

1. Read the chunk carefully and identify its PRIMARY concepts.

2. Every selected value must be explicitly supported by the chunk.

3. Never select a label simply because it is related to the chapter, the book, or the collection.

4. Collection, book, and chapter titles are provided only as context to resolve ambiguity. The chunk itself is the ground truth.

5. Do not select labels based on passing mentions or examples.

6. Multiple values are allowed only when they are equally central to the chunk.

7. For fields such as muscle or experience level, use "all" only when the chunk genuinely applies broadly and does not focus on a specific subgroup.

8. Prefer precision over completeness. It is better to return fewer correct labels than many weakly supported ones.

9. Use only the provided schema and return only the structured output.
            """,
        ),
        (
            "human",
            """
Collection:
{collection}

Book:
{book}

Chapter:
{chapter}

Chunk:
{text}
            """,
        ),
    ]
)


