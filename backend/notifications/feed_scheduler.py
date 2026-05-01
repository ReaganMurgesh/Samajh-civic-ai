"""RSS feed scheduler for automatic content ingestion."""

from typing import Dict, List
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.ingestion.document_loader import load_rss_feed
from backend.ingestion.chunker import chunk_documents
from backend.embeddings.embedder import MultilingualEmbedder
from backend.vectorstore.chroma_store import SamajhVectorStore
from backend.utils.config import config

# Real Indian govt RSS feeds (tested working)
INDIA_FEEDS: List[Dict[str, str]] = [
    {"url": "https://pib.gov.in/newsite/RSS_English.xml", "name": "PIB English", "domain": "news"},
    {"url": "https://pib.gov.in/newsite/RSS_Hindi.xml", "name": "PIB Hindi", "domain": "news"},
    {"url": "https://static.mohfw.gov.in/website/MoHFWNewsRSS.xml", "name": "MoHFW", "domain": "health"},
    {"url": "https://rbi.org.in/rss/RSS_RBI_PressReleases.xml", "name": "RBI", "domain": "finance"},
    {"url": "https://who.int/countries/india/rss", "name": "WHO India", "domain": "health"},
    {"url": "https://news.un.org/feed/subscribe/en/news/all/feed/rss.xml", "name": "UN News", "domain": "international"},
    {"url": "https://pib.gov.in/newsite/erssfeeds.aspx", "name": "PIB Schemes", "domain": "schemes"},
    {"url": "https://sebi.gov.in/rssfeeds.html", "name": "SEBI", "domain": "finance"},  # Adjust if multiple
]

class FeedScheduler:
    """Scheduler for automatic RSS ingestion."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.embedder = MultilingualEmbedder()
        self.vectorstore = SamajhVectorStore(config.chroma_persist_dir)
        self._schedule_jobs()

    def _schedule_jobs(self):
        """Schedule feeds based on frequency."""
        # High priority: hourly
        for feed in [f for f in INDIA_FEEDS if "PIB" in f["name"] or "MoHFW" in f["name"] or "RBI" in f["name"]]:
            self.scheduler.add_job(
                self.ingest_feed,
                trigger=IntervalTrigger(hours=1),
                args=(feed["url"], feed["name"], feed["domain"]),
                id=f"ingest_{feed['name'].lower().replace(' ', '_')}",
                replace_existing=True
            )

        # Medium: every 6 hours
        for feed in [f for f in INDIA_FEEDS if "WHO" in f["name"] or "UN" in f["name"]]:
            self.scheduler.add_job(
                self.ingest_feed,
                trigger=IntervalTrigger(hours=6),
                args=(feed["url"], feed["name"], feed["domain"]),
                id=f"ingest_{feed['name'].lower().replace(' ', '_')}",
                replace_existing=True
            )

        # Low: daily
        for feed in [f for f in INDIA_FEEDS if "SEBI" in f["name"]]:
            self.scheduler.add_job(
                self.ingest_feed,
                trigger=IntervalTrigger(hours=24),
                args=(feed["url"], feed["name"], feed["domain"]),
                id=f"ingest_{feed['name'].lower().replace(' ', '_')}",
                replace_existing=True
            )

    async def ingest_feed(self, url: str, source_name: str, domain: str) -> int:
        """Ingest one RSS feed: load -> chunk -> embed -> store."""
        try:
            print(f"📡 Ingesting {source_name}...")
            docs = load_rss_feed(url, source_name)
            if not docs:
                print(f"No new items from {source_name}")
                return 0

            chunks = chunk_documents(docs)
            embeddings = self.embedder.embed_chunks(chunks)
            count = self.vectorstore.add_chunks(chunks, [emb for doc, emb in embeddings])
            print(f"✅ Added {count} chunks from {source_name}")
            return count
        except Exception as e:
            print(f"❌ Error ingesting {source_name}: {e}")
            return 0

    async def run_all_feeds(self) -> Dict:
        """Run all feeds once, return summary."""
        results = {}
        for feed in INDIA_FEEDS:
            count = await self.ingest_feed(feed["url"], feed["name"], feed["domain"])
            results[feed["name"]] = count
        return results

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()


# Global instance
scheduler = FeedScheduler()

