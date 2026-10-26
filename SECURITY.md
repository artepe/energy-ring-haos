# Security policy

## Reporting a vulnerability

Please do not report security problems in public issues. Use GitHub's private vulnerability reporting (**Security → Report a vulnerability** on this repository) or contact the maintainer privately through the GitHub profile [@artepe](https://github.com/artepe). Please allow time for a fix before publishing details.

## Supported versions

Security fixes are made to the latest release and the `main` branch only.

## Security design

- The card runs inside the Home Assistant frontend and uses only the logged-in user's Home Assistant connection; it makes no other network requests and stores no credentials.
- Entity names, states and configured labels are written with `textContent`, never as HTML, so a crafted entity name cannot inject script.
