Feature: Staff posting console - post, edit, close
  As GreenJobs staff signed in through Cloudflare Access
  I want to post, edit and close jobs from a console
  So that the boards stay current without a developer

  Background:
    Given the GreenJobs platform worker with default settings
    And today is "2026-11-07"
    And the staff allow-list is "keith@greenjobs.ie, staff@greenjobs.ie"

  Scenario: Staff post a live job and it appears on the board
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I create a job titled "Solar PV Project Manager" for employer "Sunrise Energy Ltd" in "Dublin"
    Then the response status is 201
    And the created job id matches "^ie:gj:[0-9a-f-]{36}$"
    And the created job is listed on host "greenjobs.ie"
    And there is 1 audit row for action "job.create"
    And the audit log does not contain "Sunrise"

  Scenario: Retrying a create with the same Idempotency-Key does not post twice
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I create a job titled "Heat Pump Installer" with idempotency key "6f1c2a9e-1b2c-4d5e-8f90-123456789abc"
    And I create a job titled "Heat Pump Installer" with idempotency key "6f1c2a9e-1b2c-4d5e-8f90-123456789abc"
    Then the response status is 200
    And there are 1 jobs stored
    And there is 1 audit row for action "job.create"

  Scenario: Staff edit a job with the current version
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    And I have created a job titled "Energy Auditor"
    When I edit the created job setting title to "Senior Energy Auditor" at version 1
    Then the response status is 200
    And the response field "version" is 2
    And the created job is titled "Senior Energy Auditor"

  Scenario: A stale edit is refused with 409
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    And I have created a job titled "Energy Auditor"
    And I edit the created job setting title to "Senior Energy Auditor" at version 1
    When I edit the created job setting title to "Junior Energy Auditor" at version 1
    Then the response status is 409
    And the response error is "stale_version"
    And the created job is titled "Senior Energy Auditor"

  Scenario: Closing a job twice is idempotent
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    And a live job "ie:strat:1001" titled "Senior Wind Engineer" on site "ie"
    When I close job "ie:strat:1001"
    Then the response status is 200
    And the response field "already_closed" is false
    When I close job "ie:strat:1001"
    Then the response status is 200
    And the response field "already_closed" is true
    And there is 1 audit row for action "job.close"
    And the job list on host "greenjobs.ie" does not contain "ie:strat:1001"

  Scenario: A console edit of an imported job survives a later Strategies re-import
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    And a live job "ie:strat:7001" titled "Wind Engineer" on site "ie"
    When I edit job "ie:strat:7001" setting title to "Senior Wind Engineer" at version 1
    Then the response status is 200
    When the Strategies import is re-applied for job "ie:strat:7001" with title "Wind Engineer"
    Then job "ie:strat:7001" is titled "Senior Wind Engineer" with source "console"

  Scenario: A signed-in user who is not on the staff allow-list is refused
    Given I am signed in to Cloudflare Access as "intern@example.com"
    When I request the admin job list
    Then the response status is 403
    And the response error is "forbidden"

  Scenario: No Access token at all is refused
    Given I am not signed in
    When I request the admin job list
    Then the response status is 401

  Scenario Outline: A bad Access token is refused even if the header is present
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie" with a <defect> token
    When I request the admin job list
    Then the response status is 401

    Examples:
      | defect        |
      | expired       |
      | wrong-audience|
      | wrong-issuer  |
      | tampered      |
      | unsigned      |
      | foreign-key   |

  Scenario: A cross-site form cannot post a job (CSRF)
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I create a job from origin "https://evil.example"
    Then the response status is 403
    And there are 0 jobs stored

  Scenario: A write without an Idempotency-Key is refused
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I create a job without an idempotency key
    Then the response status is 400
    And the response error is "idempotency_key_required"

  Scenario: Invalid job input is refused with the field names
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I create a job titled "ab" for employer "Acme" in "Cork"
    Then the response status is 400
    And the response lists field "title"

  Scenario: A job with a javascript: apply URL is refused
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I create an external-apply job with apply URL "javascript:alert(1)"
    Then the response status is 400
    And the response lists field "apply_url"

  Scenario: Editing a job id with path traversal is refused
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I edit job "ie:gj:..%2f..%2fadmin" setting title to "Anything Here" at version 1
    Then the response status is 400
    And the response error is "invalid_id"

  Scenario: The console page is served with a strict CSP and no inline script
    Given I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I open the console
    Then the response status is 200
    And the response header "Content-Security-Policy" contains "default-src 'self'"
    And the response header "Content-Security-Policy" contains "frame-ancestors 'none'"
    And the page has no inline script

  Scenario: The admin API is rate limited
    Given the worker setting "RATE_ADMIN_PER_MIN" is "3"
    And I am signed in to Cloudflare Access as "keith@greenjobs.ie"
    When I request the admin job list 4 times
    Then the response status is 429
