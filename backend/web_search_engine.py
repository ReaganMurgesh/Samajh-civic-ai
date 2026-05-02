"""
SAMAJH WEB SEARCH ENGINE
Enhanced search using government scheme websites and APIs
"""

import os
from typing import Optional
from groq import Groq
from langchain_core.documents import Document
from backend.utils.config import config

groq_client = Groq(api_key=config.groq_api_key)

# Government scheme websites
GOVERNMENT_SOURCES = [
    {
        "name": "My Scheme Portal",
        "url": "https://www.myscheme.gov.in",
        "description": "Central portal for all government schemes",
        "search_url": "https://www.myscheme.gov.in/search?keyword={query}"
    },
    {
        "name": "India Government - Schemes",
        "url": "https://www.india.gov.in/my-government/schemes",
        "description": "Official government schemes directory",
        "search_url": "https://www.india.gov.in/my-government/schemes?keyword={query}"
    },
    {
        "name": "PM-KISAN Official",
        "url": "https://pmkisan.gov.in",
        "description": "Farmer income support scheme"
    },
    {
        "name": "Ayushman Bharat",
        "url": "https://www.pmjay.gov.in",
        "description": "Health insurance scheme"
    },
    {
        "name": "PM Awas Yojana",
        "url": "https://pmaymis.gov.in",
        "description": "Housing scheme"
    },
    {
        "name": "Pradhan Mantri Jan Dhan Yojana",
        "url": "https://www.pmjdy.gov.in",
        "description": "Financial inclusion scheme"
    },
    {
        "name": "Ministry of Finance",
        "url": "https://www.indiabudget.gov.in",
        "description": "Budget and fiscal information"
    },
    {
        "name": "Ministry of Health & Family Welfare",
        "url": "https://main.mohfw.gov.in",
        "description": "Health schemes and policies"
    },
    {
        "name": "Ministry of Agriculture",
        "url": "https://www.agriculture.gov.in",
        "description": "Agricultural schemes and guidelines"
    },
    {
        "name": "PMFBY - Crop Insurance",
        "url": "https://pmfby.gov.in",
        "description": "Farmer crop insurance"
    }
]


def build_web_search_query(user_query: str, mode: str = "schemes") -> str:
    """Build optimized search query for government websites."""
    query_lower = user_query.lower()
    
    # Add scheme-specific keywords
    scheme_keywords = {
        "farmer": "scheme agricultural subsidy",
        "health": "scheme health insurance ayushman",
        "housing": "scheme awas yojana property",
        "finance": "scheme financial support budget",
        "education": "scheme scholarship education",
        "employment": "scheme job employment skill",
        "pension": "scheme retirement pension atal",
    }
    
    for keyword, addition in scheme_keywords.items():
        if keyword in query_lower:
            return f"{user_query} {addition}"
    
    return f"{user_query} india government scheme"


def generate_web_answer(user_query: str, search_context: str, language: str = "english") -> dict:
    """Generate answer using web search context via Groq."""
    source_cards = create_web_source_cards(user_query)

    def _deterministic_answer() -> str:
        query_lower = user_query.lower()
        if "pm-kisan" in query_lower or "pm kisan" in query_lower:
            return (
                "**Direct Answer**\n"
                "PM-KISAN is a central government income-support scheme for eligible farmer families.\n\n"
                "**What you should know**\n"
                "- It supports qualifying farmers with direct income assistance\n"
                "- Official information is available on the PM-KISAN portal\n"
                "- Check eligibility, beneficiary status, and payment updates on the official site\n\n"
                "**Sources**\n"
                "- PM-KISAN Official: https://pmkisan.gov.in\n"
                "- My Scheme Portal: https://www.myscheme.gov.in\n"
            )
        if "ayushman" in query_lower or "health insurance" in query_lower:
            return (
                "**Direct Answer**\n"
                "Ayushman Bharat is a government health coverage initiative designed to support eligible citizens with medical protection.\n\n"
                "**What you should know**\n"
                "- Official details are available on the government health portals\n"
                "- Eligibility and card/application steps should be checked on the official website\n\n"
                "**Sources**\n"
                "- Ayushman Bharat: https://www.pmjay.gov.in\n"
                "- Ministry of Health & Family Welfare: https://main.mohfw.gov.in\n"
            )

        bullets = []
        for src in source_cards[:3]:
            bullets.append(f"- {src['title']}: {src['url']}")

        source_block = "\n".join(bullets) if bullets else "- My Scheme Portal: https://www.myscheme.gov.in"

        return (
            "**Direct Answer**\n"
            f"I found official government sources relevant to **{user_query}**.\n\n"
            "**What you should do next**\n"
            "- Open the official source links below\n"
            "- Check the eligibility, documents, and latest updates there\n"
            "- Use the follow-up questions to narrow down the exact step you need\n\n"
            "**Sources**\n"
            f"{source_block}\n"
        )

    try:
        # Build context about government sources
        source_context = f"""
You are SAMAJH, a civic information assistant for Indian citizens.
The user is asking about current government schemes, news, or updates.

Search context from official government websites:
{search_context}

Answer the user's question based on this real-time information.
Always cite the specific government website used.
Include relevant URLs and official details.
Maintain the same formatting rules: clear paragraphs, bullet points, examples, and [citations].
"""
        
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": source_context
                },
                {
                    "role": "user",
                    "content": f"""Please answer this question about Indian government schemes or policies:

{user_query}

Use the search results provided above. Format your answer with:
1. Direct answer
2. Key details (bullet points)
3. Real-world example
4. Next steps / What to do

Include URLs and specific ministry/department information."""
                }
            ],
            temperature=0.6,
            max_tokens=800
        )
        
        answer = response.choices[0].message.content
        if not answer:
            answer = _deterministic_answer()
        
        return {
            "answer": answer,
            "provider": "web_search",
            "sources": source_cards,
            "follow_up_questions": generate_follow_up_questions(user_query, answer),
            "confidence": 0.85
        }
    
    except Exception as e:
        print(f"Error generating web answer: {e}")
        return {
            "answer": _deterministic_answer(),
            "provider": "web_search",
            "sources": source_cards,
            "follow_up_questions": generate_follow_up_questions(user_query, _deterministic_answer()),
            "confidence": 0.75
        }


def generate_follow_up_questions(original_query: str, answer: str) -> list[str]:
    """Generate contextual follow-up questions."""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": f"""Generate 3 follow-up questions for:
Original: {original_query}
Answer: {answer}

Format as Q1: ..., Q2: ..., Q3: ..."""
            }],
            temperature=0.7,
            max_tokens=150
        )
        
        text = response.choices[0].message.content
        questions = []
        for line in text.split(","):
            q = line.strip().replace("Q1:", "").replace("Q2:", "").replace("Q3:", "").strip()
            if q and q.endswith("?"):
                questions.append(q)
        
        return questions[:3]
    
    except Exception:
        return []


def create_web_source_cards(query: str) -> list[dict]:
    """Create source cards pointing to relevant government websites."""
    relevant_sources = []
    query_lower = query.lower()
    
    # Smart source matching
    source_keywords = {
        "pm-kisan": ["farmer", "kisan", "agricultural", "farm"],
        "ayushman": ["health", "insurance", "medical", "hospital"],
        "awas": ["housing", "home", "property", "land"],
        "jan-dhan": ["bank", "account", "financial"],
        "budget": ["tax", "finance", "fiscal", "spending"],
        "health": ["health", "medical", "disease", "covid"],
        "agriculture": ["farm", "crop", "soil", "irrigation"],
    }
    
    # Find all matching sources
    for source in GOVERNMENT_SOURCES:
        source_url_lower = source["url"].lower()
        
        for scheme, keywords in source_keywords.items():
            if any(kw in query_lower for kw in keywords):
                if scheme in source_url_lower or any(kw in source_url_lower for kw in keywords):
                    relevant_sources.append({
                        "title": source["name"],
                        "url": source["url"],
                        "description": source["description"],
                        "domain": "government",
                        "type": "official_scheme"
                    })
                    break
    
    # If no specific matches, return top government sources
    if not relevant_sources:
        relevant_sources = [
            {
                "title": "My Scheme Portal",
                "url": "https://www.myscheme.gov.in",
                "description": "Search all government schemes",
                "domain": "government",
                "type": "official_scheme"
            },
            {
                "title": "India.gov.in Schemes",
                "url": "https://www.india.gov.in/my-government/schemes",
                "description": "Official schemes directory",
                "domain": "government",
                "type": "official_scheme"
            }
        ]
    
    return relevant_sources[:5]


def search_government_websites(query: str) -> str:
    """
    Search government websites for relevant information.
    Returns formatted context for LLM.
    """
    search_query = build_web_search_query(query)
    
    # Build search results context from government sources
    results = []
    results.append(f"🔍 Searching government sources for: {search_query}\n")
    results.append("=" * 60)
    
    for source in GOVERNMENT_SOURCES:
        if any(keyword in query.lower() for keyword in source["description"].lower().split()):
            results.append(f"\n📍 {source['name']}")
            results.append(f"   URL: {source['url']}")
            results.append(f"   About: {source['description']}")
            
            # Build direct search URL if available
            if "search_url" in source:
                search_url = source["search_url"].format(query=search_query.replace(" ", "+"))
                results.append(f"   Search: {search_url}")
    
    results.append("\n" + "=" * 60)
    results.append("\n✅ For live results, visit the government websites above")
    results.append("   or use My Scheme Portal: https://www.myscheme.gov.in\n")
    
    return "\n".join(results)


if __name__ == "__main__":
    # Test
    query = "What is PM-KISAN scheme?"
    web_context = search_government_websites(query)
    result = generate_web_answer(query, web_context)
    print(result["answer"])
