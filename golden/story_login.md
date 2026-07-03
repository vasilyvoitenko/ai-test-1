# User Story: Login

As a registered user, I want to log in with my email and password so that I can access my home page.

## Acceptance Criteria

- Given the user enters a valid email and password, when they submit the login form, then they are redirected to the home page.
- Given the user enters a valid email and an incorrect password, when they submit the login form, then an error message is displayed.
- Given the email or password field is empty, when the user views the login form, then the submit button is disabled.
- Given the user enters an incorrect password 5 times, when they try to submit the login form again, then the account is locked for 15 minutes.
