import hashlib

from src.news_identity import canonical_article_hash


def test_canonical_article_hash_uses_verbatim_ticker_title_and_date10():
    assert canonical_article_hash(
        "HAPN", "Title With Case ", "2026-06-27T23:59:59+0000"
    ) == hashlib.sha256(b"HAPN|Title With Case |2026-06-27").hexdigest()


def test_direct_and_migration_share_the_same_hash_function():
    import src.news_providers as providers
    from scripts import migrate_to_supabase as migration

    assert providers.canonical_article_hash is canonical_article_hash
    assert migration.article_hash is canonical_article_hash
