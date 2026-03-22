from app.services.parser import RemoteOkParser


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

JSON_FEED = """
[
  {
    "last_updated": 1774166402,
    "legal": "Public feed metadata"
  },
  {
    "id": "1130857",
    "date": "2026-03-21T00:00:11+00:00",
    "company": "Vanta",
    "position": "Brand Designer",
    "location": "Worldwide",
    "salary_min": 120000,
    "salary_max": 150000,
    "tags": ["design", "figma"],
    "url": "https://remoteok.com/remote-jobs/1130857",
    "description": "<p>Design brand systems in Figma.</p>"
  }
]
"""


def test_parser_handles_malformed_and_partial_rows_without_crashing():
    parser = RemoteOkParser("https://remoteok.com")

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


def test_parser_supports_public_json_feed_records():
    parser = RemoteOkParser("https://remoteok.com")

    jobs = parser.parse_jobs(JSON_FEED)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_job_id == "1130857"
    assert job.source_job_url == "https://remoteok.com/remote-jobs/1130857"
    assert job.title == "Brand Designer"
    assert job.company == "Vanta"
    assert job.location_raw == "Worldwide"
    assert job.salary_text == "$120,000 - $150,000"
    assert job.description_text == "Design brand systems in Figma."
    assert job.tags == ["design", "figma"]
    assert job.remote_type_raw == "remote"
