# artist-study-kit

## Initial Seed Idea

**artist-study-kit** is an agentic research and analysis workflow for preparing artist master studies.

The project takes the name of a historical artist as input and produces a structured study package that helps a human artist understand the artist’s biography, art-historical context, defining style, major works, and practical visual techniques before attempting a study in that artist’s manner.

The goal is not simply to collect facts or images. The goal is to convert art-historical research into usable studio preparation.

## Core Purpose

The skill should help answer four practical questions:

1. Who was this artist, and where do they sit in art history?
2. What defines their visual style?
3. What are their most important works?
4. Which works should I study closely, and what should I pay attention to when making my own study?

## Intended Workflow

### 1. Artist Background Research

Given an artist name, the skill researches the artist’s life, historical period, geography, influences, movements, and relevance within art history.

The output should include a concise but useful background report covering:

- Basic biographical facts
- Where the artist lived and worked
- Major artistic periods or movements associated with the artist
- Teachers, peers, influences, and followers
- The artist’s role in art history
- Why the artist remains important
- Recommended resources for further study

Recommended resources should include:

- Museum pages
- Academic or institutional sources
- High-quality art-history essays
- Books, catalogues, or monographs when available
- YouTube lectures, documentaries, or walkthroughs
- Other high-signal learning material

### 2. Web Source Discovery and Quality Grading

The project should include a grading system for evaluating the quality of web resources.

Many art websites are low quality for study purposes because they are overloaded with ads, optimized for search traffic, focused on poster sales, or shallow in their art-historical treatment. Auction-house pages can contain useful provenance or market data, but they are often poor as general learning sources and should be treated cautiously.

The system should score or classify sources based on criteria such as:

- Institutional authority
- Art-historical depth
- Accuracy and citation quality
- Image quality and usefulness
- Ad density and page usability
- Whether the site is primarily selling posters or reproductions
- Whether the source is primarily market-oriented, such as auction listings
- Whether the content is original analysis or low-value aggregation
- Suitability for learning and master-study preparation

The source grading system should help the user quickly distinguish between:

- High-trust sources
- Useful but limited sources
- Image-only or reference-only sources
- Commercially biased sources
- Low-quality or avoidable sources

### 3. Style Definition

The skill should analyze what visually defines the artist’s style.

This section should move beyond biography and ask what makes the artist recognizable. It should identify the formal, technical, and compositional traits that separate the artist from others.

Possible dimensions include:

- Line quality
- Shape language
- Color palette
- Value structure
- Light and shadow
- Brushwork or mark-making
- Composition
- Perspective and spatial construction
- Figure treatment
- Gesture
- Abstraction versus realism
- Surface texture
- Use of symbolism
- Emotional tone
- Subject matter
- Materials and process
- Historical or technical innovations

The goal is to bring the artist’s visual grammar to the front of the user’s mind before beginning a study.

### 4. Important Works Inventory

The skill should produce a list of the artist’s most important works.

For each work, the report should ideally include:

- Title
- Date
- Medium
- Dimensions, when available
- Current location or collection
- Why the work matters
- Relationship to the artist’s development
- High-quality source pages for the work
- Notes about available image quality

This section should support later image collection and human curation.

### 5. Image Discovery and Collection

The project should include a Python-based image discovery component that searches for high-resolution images of the artist’s major works and collects candidate files into a local directory for browsing.

This component should prioritize legally and ethically accessible public web resources, especially museum and institutional image sources when available.

The image collection step should attempt to gather:

- Large image files
- Museum-hosted images
- Public domain or open-access images where available
- Multiple versions of major works when useful for comparison
- Metadata about the source page and image URL
- Notes about image size, quality, and trust level

The collected images should be organized into a directory structure suitable for manual review.

Example structure:

```text
artist-study-kit/
  studies/
    artist-name/
      report.md
      sources/
        sources.json
        source-grades.md
      images/
        candidates/
        selected/
      analysis/
        selected-works.md
```

### 6. Human Curation Step

The workflow should explicitly include a human-in-the-loop curation phase.

After the image discovery process creates a candidate gallery, the user reviews the image pool and selects the works that are most compelling or useful for study.

The user should be able to refine the pool into a short list of selected images for deeper analysis.

This step matters because the final study should be based not only on art-historical importance, but also on the user’s own interest, taste, learning goals, and practical studio intent.

### 7. Deep Visual Analysis of Selected Works

After the user selects a short list of works, the skill performs deeper analysis on those images.

The analysis should draw on art and design principles, including:

- Composition
- Visual hierarchy
- Balance
- Rhythm
- Proportion
- Gesture
- Edge control
- Focal points
- Color harmony
- Value grouping
- Shape design
- Use of negative space
- Pattern and repetition
- Surface handling
- Implied movement
- Emotional effect
- Technical execution

For each selected work, the skill should produce notes that help the user prepare to make a study.

The output should answer:

- What is the image doing visually?
- What should I notice first?
- What are the dominant design decisions?
- What techniques should I try to imitate?
- What traps or misunderstandings should I avoid?
- What exercises could help me internalize this style?

## Expected Outputs

A completed artist study package may include:

- `report.md` — full artist background and style report
- `sources.md` — recommended sources with quality grades
- `works.md` — important works inventory
- `images/` — collected candidate images
- `selected/` — human-curated image shortlist
- `analysis.md` — deep analysis of selected works
- `study-notes.md` — practical notes for making a master study
- `prompts/` — reusable prompts for agentic research and critique

## Design Principles

The project should be:

- **Research-grounded** — prefer museums, libraries, universities, and serious art-history sources.
- **Anti-slop** — penalize ad-heavy, shallow, SEO-driven, poster-selling, and low-value aggregation sites.
- **Studio-oriented** — convert research into practical visual guidance.
- **Human-curated** — keep the artist-user in control of final image selection.
- **Reproducible** — produce durable files and structured directories.
- **Extensible** — allow future support for different artists, media, periods, and study types.
- **Agentic** — automate discovery, grading, collection, and first-pass analysis while preserving human judgment.

## Initial Scope

The first version should focus on a single artist at a time.

Minimum viable workflow:

1. Accept artist name.
2. Research background and art-historical context.
3. Recommend and grade web resources.
4. Identify important works.
5. Search for high-quality images of those works.
6. Save candidate images and metadata.
7. Let the human select a short list.
8. Produce detailed visual analysis of the selected works.
9. Generate study preparation notes.

## Possible Future Enhancements

Future versions could add:

- Better museum API integrations
- IIIF image support
- Local image gallery generation
- OCR or metadata extraction
- Comparison across multiple artists
- Automatic palette extraction
- Composition thumbnails and diagrams
- Style checklists
- Study exercise generation
- Integration with Obsidian or other note systems
- LLM-as-judge evaluation of source quality and analysis depth
- Personal study history and skill progression tracking

## Working Description

A reproducible workflow for artist background research, web-source scoring, masterwork discovery, image curation, and style-study preparation.
