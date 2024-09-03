# dbrownell_Common

<!-- BEGIN: Exclude Package -->
[![License](https://img.shields.io/github/license/davidbrownell/dbrownell_Common?color=dark-green)](https://github.com/davidbrownell/dbrownell_Common/blob/master/LICENSE.txt)
[![GitHub commit activity](https://img.shields.io/github/commit-activity/y/davidbrownell/dbrownell_Common?color=dark-green)](https://github.com/davidbrownell/dbrownell_Common/commits/main/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dbrownell_Common?color=dark-green)](https://pypi.org/project/dbrownell_Common/)
[![PyPI - Version](https://img.shields.io/pypi/v/dbrownell_Common?color=dark-green)](https://pypi.org/project/dbrownell_Common/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/dbrownell_Common)](https://pypistats.org/packages/dbrownell_Common)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/9412/badge)](https://www.bestpractices.dev/projects/9412)
[![Code Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/davidbrownell/f15146b1b8fdc0a5d45ac0eb786a84f7/raw/dbrownell_Common_coverage.json)](https://github.com/davidbrownell/dbrownell_Common/actions)
<!-- END: Exclude Package -->

Common python functionality used across a number of different packages.

<!-- BEGIN: Exclude Package -->
## Contents
- [Overview](#overview)
- [Installation](#installation)
- [Development](#development)
- [Additional Information](#additional-information)
- [License](#license)
<!-- END: Exclude Package -->

## Overview
TODO: Complete this section

### How to use dbrownell_Common
TODO: Complete this section

<!-- BEGIN: Exclude Package -->
## Installation
dbrownell_Common can be installed via one of these methods:

- [Installation via Executable](#installation-via-executable)
- [Installation via pip](#installation-via-pip)

### Installation via Executable
Download an executable for Linux, MacOS, or Windows to the the functionality provided by this repository without a dependency on python.

1. Download the archive for the latest release [here](https://github.com/davidbrownell/dbrownell_Common/releases/latest). The filename will begin with `exe.` and contain the name of your operating system.
2. Decompress the archive.

#### Verifying Signed Executables
Executables are signed and validated using [Minisign](https://jedisct1.github.io/minisign/). The public key used to verify the signature of the executable is `RWR7Q3JA96yWUygMCtHziHfdrpNeUzZoU6MHyayTCvv1K8MWoGYVoTGw`.

To verify that the executable is valid, download the corresponding `.minisig` file [here](https://github.com/davidbrownell/dbrownell_Common/releases/latest) and run this command, replacing `<filename>` with the name of the file to be verified:

`docker run -i --rm -v .:/host jedisct1/minisign -V -P RWR7Q3JA96yWUygMCtHziHfdrpNeUzZoU6MHyayTCvv1K8MWoGYVoTGw -m /host/<filename>`

Instructions for installing [docker](https://docker.com) are available at https://docs.docker.com/engine/install/.

### Installation via pip
To install the dbrownell_Common package via [pip](https://pip.pypa.io/en/stable/) (Python Installer for Python) for use with your python code:

`pip install dbrownell_Common`


## Development
Please visit [Contributing](https://github.com/davidbrownell/dbrownell_Common/blob/main/CONTRIBUTING.md) and [Development](https://github.com/davidbrownell/dbrownell_Common/blob/main/DEVELOPMENT.md) for information on contributing to this project.
<!-- END: Exclude Package -->

## Additional Information
Additional information can be found at these locations.

| Title | Document | Description |
| --- | --- | --- |
| Code of Conduct | [CODE_OF_CONDUCT.md](https://github.com/davidbrownell/dbrownell_Common/blob/main/CODE_OF_CONDUCT.md) | Information about the the norms, rules, and responsibilities we adhere to when participating in this open source community. |
| Contributing | [CONTRIBUTING.md](https://github.com/davidbrownell/dbrownell_Common/blob/main/CONTRIBUTING.md) | Information about contributing code changes to this project. |
| Development | [DEVELOPMENT.md](https://github.com/davidbrownell/dbrownell_Common/blob/main/DEVELOPMENT.md) | Information about development activities involved in making changes to this project. |
| Governance | [GOVERNANCE.md](https://github.com/davidbrownell/dbrownell_Common/blob/main/GOVERNANCE.md) | Information about how this project is governed. |
| Maintainers | [MAINTAINERS.md](https://github.com/davidbrownell/dbrownell_Common/blob/main/MAINTAINERS.md) | Information about individuals who maintain this project. |
| Security | [SECURITY.md](https://github.com/davidbrownell/dbrownell_Common/blob/main/SECURITY.md) | Information about how to privately report security issues associated with this project. |

## License

dbrownell_Common is licensed under the <a href="https://choosealicense.com/licenses/mit/" target="_blank">MIT</a> license.
