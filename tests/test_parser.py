from app.services.multi_source_fetcher import SourcePayload
from app.services.parser import PublicJobParser


MALFORMED_HTML = """
<html>
  <body>
    <table>
      <tr class="job" data-id="id-only"></tr>
      <tr class="job">
        <td class="company">
          <a href="javascript:void(0)">
            <h3 itemprop="name">Broken Link Co</h3>
          </a>
          <div class="location"></div>
          <div class="description"></div>
          <div class="tags">
            <h3> </h3>
          </div>
        </td>
      </tr>
      <tr class="job" data-job-id="attr-only" data-position="Backend Developer" data-company="Attr Co" data-location="Remote" data-tags="Python, , FastAPI" data-date="not-a-date"></tr>
      <tr class="job"></tr>
    </table>
  </body>
</html>
"""

ARBEITNOW_FEED = """
{
  "jobs": [
    {
      "id": "1001",
      "title": "Senior Python Backend Engineer",
      "company_name": "Acme",
      "location": "Berlin, Germany",
      "remote": true,
      "tags": ["Python", "FastAPI", "Docker"],
      "url": "https://example.com/jobs/1001",
      "created_at": "2026-03-20T10:00:00+00:00"
    }
  ]
}
"""

REMOTIVE_FEED = """
{
  "jobs": [
    {
      "id": "2001",
      "title": "Data Engineer",
      "company_name": "Beta Analytics",
      "candidate_required_location": "United Kingdom",
      "job_type": "contract",
      "tags": ["SQL", "Python"],
      "url": "https://example.com/jobs/2001",
      "publication_date": "2026-03-18T08:00:00+00:00"
    }
  ]
}
"""

THEMUSE_FEED = """
{
  "results": [
    {
      "id": 3001,
      "name": "Product Designer",
      "company": { "name": "Muse Labs" },
      "locations": [
        { "name": "Remote" },
        { "name": "New York, NY" }
      ],
      "refs": { "landing_page": "https://example.com/jobs/3001" },
      "publication_date": "2026-03-17T09:30:00+00:00"
    }
  ]
}
"""


def test_parser_handles_malformed_and_partial_rows_without_crashing():
    parser = PublicJobParser("https://remoteok.com")

    jobs = parser.parse_jobs(MALFORMED_HTML)

    assert len(jobs) == 3

    id_only_job = next(job for job in jobs if job.source_job_id == "id-only")
    assert id_only_job.title is None
    assert id_only_job.company is None
    assert id_only_job.source_job_url is None

    broken_link_job = next(job for job in jobs if job.company == "Broken Link Co")
    assert broken_link_job.source_job_url is None
    assert broken_link_job.description_text is None
    assert broken_link_job.tags == []

    attribute_only_job = next(job for job in jobs if job.source_job_id == "attr-only")
    assert attribute_only_job.title == "Backend Developer"
    assert attribute_only_job.company == "Attr Co"
    assert attribute_only_job.location_raw == "Remote"
    assert attribute_only_job.tags == ["Python", "FastAPI"]
    assert attribute_only_job.posted_at_raw == "not-a-date"


def test_parser_supports_multiple_public_json_sources():
    parser = PublicJobParser()

    jobs = parser.parse_source_payloads(
        [
            SourcePayload(source="arbeitnow", url="https://www.arbeitnow.com/api/job-board-api", body=ARBEITNOW_FEED),
            SourcePayload(source="remotive", url="https://remotive.com/api/remote-jobs", body=REMOTIVE_FEED),
            SourcePayload(source="themuse", url="https://www.themuse.com/api/public/jobs?page=1", body=THEMUSE_FEED),
        ]
    )

    assert len(jobs) == 3

    arbeitnow_job = next(job for job in jobs if job.source == "arbeitnow")
    assert arbeitnow_job.title == "Senior Python Backend Engineer"
    assert arbeitnow_job.company == "Acme"
    assert arbeitnow_job.location_raw == "Berlin, Germany"
    assert arbeitnow_job.tags == ["Python", "FastAPI", "Docker"]
    assert arbeitnow_job.remote_type_raw == "remote"

    remotive_job = next(job for job in jobs if job.source == "remotive")
    assert remotive_job.title == "Data Engineer"
    assert remotive_job.company == "Beta Analytics"
    assert remotive_job.location_raw == "United Kingdom"
    assert remotive_job.employment_type_raw == "contract"
    assert remotive_job.remote_type_raw == "remote"

    themuse_job = next(job for job in jobs if job.source == "themuse")
    assert themuse_job.title == "Product Designer"
    assert themuse_job.company == "Muse Labs"
    assert themuse_job.location_raw == "Remote, New York, NY"
    assert themuse_job.source_job_url == "https://example.com/jobs/3001"
