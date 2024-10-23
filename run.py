# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

import os
import signal
import argparse
import subprocess
from dotenv import load_dotenv
from pathlib import Path

VENDOR = "valory"
AGENT_NAME = "impact_evaluator"
SERVICE_NAME = "impact_evaluator"


def run_agent():
    subprocess.run(["rm", "-r", AGENT_NAME])
    subprocess.run(["find", ".", "-empty", "-type", "d", "-delete"])
    subprocess.run(["autonomy", "packages", "lock"])
    subprocess.run(["autonomy", "fetch", "--local", "--agent", f"{VENDOR}/{AGENT_NAME}"])
    os.chdir(AGENT_NAME)
    subprocess.run(["cp", "../ethereum_private_key.txt", "."])
    subprocess.run(["autonomy", "add-key", "ethereum", "ethereum_private_key.txt"])
    subprocess.run(["autonomy", "issue-certificates"])
    subprocess.run(["aea", "-s", "run"])

def find_abci_build_folder(directory):
    for folder in os.listdir(directory):
        if folder.startswith("abci_build_") and os.path.isdir(os.path.join(directory, folder)):
            return folder
    return None

def run_service():
    # Set env vars
    load_dotenv(dotenv_path=Path(".env"))

    # Push packages and fetch service
    subprocess.run(["make", "clean"])

    subprocess.run(["autonomy", "push-all"])

    subprocess.run(["autonomy", "fetch", "--local", "--service", f"{VENDOR}/{SERVICE_NAME}"])
    os.chdir(SERVICE_NAME)

    # Build the image
    subprocess.run(["autonomy", "build-image"])

    # Copy the keys and build the deployment
    subprocess.run(["cp", "../keys.json", "."])
    subprocess.run(["autonomy", "deploy", "build", "-ltm"])

    # Run the deployment
    p = None
    try:
        # p = subprocess.run(["autonomy", "deploy", "run", "--build-dir", "abci_build/"])
        abci_folder = find_abci_build_folder(os.curdir)
        if abci_folder is None:
            raise Exception("Could not find abci_build folder!")
        p = subprocess.Popen(["autonomy", "deploy", "run", "--build-dir", abci_folder], shell=False)
    except KeyboardInterrupt:
        p.send_signal(signal.SIGINT)
        p.wait()


def main():

    parser = argparse.ArgumentParser(description="Run IEKit agent and service")
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument("-a", "--agent", action="store_true", help="Run agent")
    type_group.add_argument("-s", "--service", action="store_true", help="Run service")
    parser.add_argument('-d', '--dev', action="store_true", help="Dev mode")

    args = parser.parse_args()

    if args.agent:
        run_agent()

    if args.service:
        run_service()


if __name__ == "__main__":
    main()
