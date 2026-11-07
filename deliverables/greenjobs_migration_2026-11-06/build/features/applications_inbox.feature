Feature: Applications are routed to an inbox
  As an employer or GreenJobs consultant
  I want every genuine application to reach the right inbox exactly once
  So that no candidate is lost and nobody is emailed twice

  Background:
    Given the GreenJobs platform worker with default settings
    And today is "2026-11-07"
    And the site inbox for "ie" is "jobs@greenjobs.ie"
    And a live job "ie:strat:1001" titled "Senior Wind Engineer" on site "ie"
    And a candidate "Aoife Byrne" with email "aoife@example.ie" applying to job "ie:strat:1001"

  Scenario: Dry run is the default - the application is stored and nothing is sent
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 201
    And 1 application is stored routed to "jobs@greenjobs.ie"
    And the application delivery status is "dry_run"
    And no email is sent
    And the spend ledger shows 0 sends

  Scenario: Live sending needs both DRY_RUN=0 and LIVE_CONFIRM
    Given the worker setting "DRY_RUN" is "0"
    When the candidate submits the application on host "greenjobs.ie"
    Then no email is sent
    And the application delivery status is "dry_run"

  Scenario: With both live switches set, exactly one email goes to the site inbox
    Given the worker setting "DRY_RUN" is "0"
    And the worker setting "LIVE_CONFIRM" is "send-applications"
    And the candidate attaches a "pdf" CV
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 201
    And 1 email is sent to "jobs@greenjobs.ie"
    And the email reply-to is "aoife@example.ie"
    And the spend ledger shows 1 sends
    And the application delivery status is "sent"

  Scenario: A duplicate application sends no second email
    Given the worker setting "DRY_RUN" is "0"
    And the worker setting "LIVE_CONFIRM" is "send-applications"
    When the candidate submits the application on host "greenjobs.ie"
    And the candidate submits the application again with email "AOIFE@Example.ie"
    Then the response status is 200
    And the response field "status" is "already_received"
    And 1 email is sent to "jobs@greenjobs.ie"
    And 1 application is stored routed to "jobs@greenjobs.ie"

  Scenario: Consultant routing uses the job's apply email
    Given the worker setting "APPLY_ROUTING" is "consultant"
    And a live job "ie:strat:1002" titled "Grid Engineer" on site "ie" with apply email "consultant@agency.ie"
    And the candidate is applying to job "ie:strat:1002"
    When the candidate submits the application on host "greenjobs.ie"
    Then 1 application is stored routed to "consultant@agency.ie"

  Scenario: Consultant routing falls back to the site inbox and audits it
    Given the worker setting "APPLY_ROUTING" is "consultant"
    When the candidate submits the application on host "greenjobs.ie"
    Then 1 application is stored routed to "jobs@greenjobs.ie"
    And there is 1 audit row for action "application.route_fallback"

  Scenario: A job that applies on an external site refuses on-site applications
    Given a live job "ie:strat:1003" titled "External Role" on site "ie" applying via "https://careers.example.ie/3"
    And the candidate is applying to job "ie:strat:1003"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 409
    And the response error is "apply_externally"
    And 0 applications are stored

  Scenario: A closed job takes no applications
    Given a closed job "ie:strat:1004" titled "Closed Role" on site "ie"
    And the candidate is applying to job "ie:strat:1004"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 404
    And 0 applications are stored

  Scenario: The honeypot field catches a bot
    Given the candidate fills the hidden "website" field with "http://spam.example"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 400
    And 0 applications are stored
    And no email is sent

  Scenario: A form submitted under 3 seconds after render is refused
    Given the form was rendered 1 seconds ago
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 400
    And the response error is "too_fast"
    And 0 applications are stored

  Scenario: Consent is required
    Given the candidate has not ticked consent
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 400
    And the response lists field "consent"

  Scenario: An email header injection in the name is refused
    Given the candidate's name is "Aoife\r\nBcc: victim@example.com"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 400
    And the response lists field "name"

  Scenario: An oversize CV is refused
    Given the worker setting "MAX_CV_BYTES" is "1000"
    And the candidate attaches a CV of 1001 bytes
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 413
    And the response error is "cv_too_large"
    And no CV is stored

  Scenario: An executable renamed to .pdf is refused by its magic bytes
    Given the candidate attaches an executable named "cv.pdf"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 415
    And no CV is stored
    And 0 applications are stored

  Scenario Outline: Accepted CV types are stored under a generated key, never the client file name
    Given the candidate attaches a "<type>" CV named "../../<type>-evil.<type>"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 201
    And the stored CV key matches "^cv/ie/2026/11/[0-9a-f-]{36}\.<type>$"

    Examples:
      | type |
      | pdf  |
      | doc  |
      | docx |

  Scenario: A traversal job id in the form is refused
    Given the candidate is applying to job "../../etc/passwd"
    When the candidate submits the application on host "greenjobs.ie"
    Then the response status is 400
    And the response error is "invalid_id"

  Scenario: Six applications from one IP in ten minutes hit the rate limit
    When 6 different candidates apply from IP "203.0.113.50" on host "greenjobs.ie"
    Then the response status is 429
    And 5 applications are stored

  Scenario: An unknown host takes no applications
    When the candidate submits the application on host "apply.attacker.example"
    Then the response status is 404
    And the response error is "unknown_host"
    And 0 applications are stored
