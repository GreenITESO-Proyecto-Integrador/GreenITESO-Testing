# GreenITESO Testing

This repository contains the shared end-to-end testing framework for the three GreenITESO teams. Its current conventions and setup are in [CLAUDE.md](CLAUDE.md).

The [peer-testing protocol](docs/peer-testing-protocol-proposal.md) is a proposal for team review. It does not establish a required release gate or replace the current repository and project rules.

For the current class cycle, start with the [team rotation, test cases, and prior QA evidence](docs/peer-testing-friday.md).

## Docker

Build the Linux test image:

```sh
docker build -t greeniteso-testing .
```

By default, the image collects the Dashboard test module:

```sh
docker run --rm greeniteso-testing
```

To run or collect a different pytest selection, pass pytest arguments after the image name:

```sh
docker run --rm greeniteso-testing tests/Dashboard/test_Dashboard.py
docker run --rm greeniteso-testing --collect-only -q tests/Dashboard/test_Dashboard.py
```

For an authenticated or mock environment, pass the repository `.env` with `--env-file` and mount a persistent auth-state directory when using `AUTH_MODE=refresh`:

```sh
docker run --rm --env-file .env -v "$HOME/.greeniteso-e2e/auth:/root/.greeniteso-e2e/auth" greeniteso-testing tests/Dashboard/test_Dashboard.py
```

The container installs Chromium for Playwright. Browser execution still requires a reachable `BASE_URL`, valid test accounts or the disposable mock stack, and safe `E2E_CLEANUP` configuration.
