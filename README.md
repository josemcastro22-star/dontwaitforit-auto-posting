# Don't Wait For It Foundation — Instagram Auto-Poster

Automated Instagram posting system for [@dontwaitforit_foundation](https://www.instagram.com/dontwaitforit_foundation/).

## What It Does

Runs one command → AI generates a branded infographic → posts to Instagram automatically.

- **Monday** — Mindset and mental health for the SCI community
- **Tuesday** — New spinal cord injury research and discoveries
- **Wednesday** — Adaptive equipment and assistive technology
- **Thursday** — SCI statistics and awareness

## How to Run

    python3 post.py

## Tech Stack

- **Python** — core script
- **Claude API (Anthropic)** — AI content generation
- **Pillow** — infographic image generation
- **Meta Graph API** — Instagram posting
- **GitHub Pages** — free public image hosting
- **GitHub Actions** — cloud scheduling

## Environment Variables

Create a .env file with:

    IG_ACCESS_TOKEN=your_page_access_token
    IG_USER_ID=your_instagram_user_id
    ANTHROPIC_API_KEY=your_anthropic_key
    PAGES_BASE_URL=https://josemcastro22-star.github.io/dontwaitforit-auto-posting
    GITHUB_TOKEN=your_github_token
    GITHUB_REPOSITORY=josemcastro22-star/dontwaitforit-auto-posting

## About the Foundation

[Don't Wait For It Foundation](https://dontwaitforit.org) is a 501(c)(3) nonprofit providing financial assistance for physical therapy and adaptive equipment to individuals with spinal cord injuries.
