from scripts.firecrawl_fetch import FetchedPage
from scripts.source_signals import SHORTLIST_DOMAINS, scan_source


def _page(url, markdown):
    return FetchedPage(url=url, final_url=url, status_code=200, markdown=markdown, metadata={})


def test_shortlist_domains_include_seeds():
    assert "smarthistory.org" in SHORTLIST_DOMAINS
    assert "metmuseum.org" in SHORTLIST_DOMAINS


def test_museum_page_scores_high_and_skips_llm():
    md = "Provenance and bibliography. See footnotes [1] [2]. References: catalogue raisonné."
    scan = scan_source(_page("https://www.metmuseum.org/art/collection/123", md))
    assert scan.shortlisted is True
    assert scan.tld_trust == "trusted"
    assert scan.citation_count >= 2
    assert scan.band == "high"
    assert scan.needs_llm_review is False


def test_commerce_page_scores_low_and_skips_llm():
    md = "Add to cart. Buy now. Price: $4,500. Make an offer. Shipping calculated at checkout."
    scan = scan_source(_page("https://auction-house.com/lot/77", md))
    assert scan.commerce_hits  # non-empty
    assert scan.tld_trust == "commercial"
    assert scan.band == "low"
    assert scan.needs_llm_review is False


def test_commerce_hits_are_human_labels_not_regex():
    md = "Senecio print $45.00. Add to cart. Estimate: $4,500."
    scan = scan_source(_page("https://shop.example.com/p", md))
    assert "add to cart" in scan.commerce_hits
    assert "listed price" in scan.commerce_hits
    # no raw regex metacharacters leak into the human-readable hits
    assert all("\\" not in h and "$" not in h for h in scan.commerce_hits)


def test_neutral_page_is_borderline_and_needs_llm():
    md = "An essay about the artist with some discussion and one footnote [1]."
    scan = scan_source(_page("https://some-blog.net/essay", md))
    assert scan.band == "borderline"
    assert scan.needs_llm_review is True


def test_domain_and_tld_parsed_from_url():
    scan = scan_source(_page("https://www.rijksmuseum.nl/en/page", "text"))
    assert scan.domain == "rijksmuseum.nl"
    assert scan.tld == "nl"
