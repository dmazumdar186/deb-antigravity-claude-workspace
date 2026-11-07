Feature: Boards on Keith's domains show current jobs
  As a job seeker on greenjobs.ie or greenjobs.co.uk
  I want to see only the jobs that are open today on the board for that domain
  So that I never waste time on a closed, draft or foreign-site listing

  Background:
    Given the GreenJobs platform worker with default settings
    And today is "2026-11-07"
    And a live job "ie:strat:1001" titled "Senior Wind Engineer" on site "ie"
    And a live job "ie:strat:1002" titled "Grid Connections Lead" on site "ie" closing "2026-11-30"
    And a closed job "ie:strat:1003" titled "Hydrogen Analyst" on site "ie"
    And a draft job "ie:strat:1004" titled "Draft Heat Pump Role" on site "ie"
    And a live job "ie:strat:1005" titled "Expired Solar Role" on site "ie" closing "2026-11-06"
    And a live job "uk:strat:2001" titled "Offshore Wind Planner" on site "uk"

  Scenario: The Irish board lists only live, unexpired Irish jobs
    When a visitor requests "/api/jobs" on host "greenjobs.ie"
    Then the response status is 200
    And the job list contains "ie:strat:1001"
    And the job list contains "ie:strat:1002"
    And the job list does not contain "ie:strat:1003"
    And the job list does not contain "ie:strat:1004"
    And the job list does not contain "ie:strat:1005"
    And the job list does not contain "uk:strat:2001"

  Scenario: The UK board lists only UK jobs
    When a visitor requests "/api/jobs" on host "www.greenjobs.co.uk"
    Then the response status is 200
    And the job list contains "uk:strat:2001"
    And the job list does not contain "ie:strat:1001"

  Scenario: Listed jobs have the static site's jobs.json shape
    When a visitor requests "/api/jobs" on host "greenjobs.ie"
    Then every listed job has exactly the fields "id, title, employer, location, type, sal_text, sectors, posted, closing, summary"

  Scenario: A job closing today is still listed
    Given a live job "ie:strat:1006" titled "Last Day Role" on site "ie" closing "2026-11-07"
    When a visitor requests "/api/jobs" on host "greenjobs.ie"
    Then the job list contains "ie:strat:1006"

  Scenario: A closed job's detail page is not found
    When a visitor requests "/api/jobs/ie:strat:1003" on host "greenjobs.ie"
    Then the response status is 404
    And the response error is "not_found"

  Scenario: A live job's detail is served with an escaped description
    Given a live job "ie:strat:1007" titled "Script Test Role" on site "ie" with description "<script>alert(1)</script> and enough words to pass"
    When a visitor requests "/api/jobs/ie:strat:1007" on host "greenjobs.ie"
    Then the response status is 200
    And the response field "description_html" does not contain "<script>"

  Scenario: An Irish job is not served on the UK domain
    When a visitor requests "/api/jobs/ie:strat:1001" on host "greenjobs.co.uk"
    Then the response status is 404

  Scenario: An unknown host is refused
    When a visitor requests "/api/jobs" on host "greenjobs.example.net"
    Then the response status is 404
    And the response error is "unknown_host"

  Scenario Outline: Path traversal in a job id is rejected
    When a visitor requests "/api/jobs/<id>" on host "greenjobs.ie"
    Then the response status is 400
    And the response error is "invalid_id"

    Examples:
      | id                       |
      | ie:strat:..%2f..%2fetc   |
      | ie:strat:%252e%252e      |
      | ie%3Astrat%3A1%5C..      |
      | ..%5Cwindows             |

  Scenario: A foreign website cannot read the board cross-origin
    When a visitor from origin "https://evil.example" requests "/api/jobs" on host "greenjobs.ie"
    Then the response status is 403

  Scenario: The static rebuild export needs the build token
    When the static build requests the export for site "ie" with token "wrong-token"
    Then the response status is 401
    When the static build requests the export for site "ie" with the configured token
    Then the response status is 200
    And the job list contains "ie:strat:1001"
    And the job list does not contain "ie:strat:1003"

  Scenario: Job alerts are switched off for go-live
    When a visitor posts to "/api/alerts" on host "greenjobs.ie"
    Then the response status is 404
