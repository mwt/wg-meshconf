#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Name: Database Manager
Creator: K4YT3X
Date Created: July 19, 2020
Last Modified: June 16, 2021
"""

import copy
import csv
import ipaddress
import itertools
import pathlib
import sys

from rich.console import Console
from rich.table import Table

from .wireguard import WireGuard

INTERFACE_ATTRIBUTES = [
    "Address",
    "ListenPort",
    "FwMark",
    "PrivateKey",
    "DNS",
    "MTU",
    "Table",
    "PreUp",
    "PostUp",
    "PreDown",
    "PostDown",
    "SaveConfig",
]

INTERFACE_OPTIONAL_ATTRIBUTES = [
    "ListenPort",
    "FwMark",
    "DNS",
    "MTU",
    "Table",
    "PreUp",
    "PostUp",
    "PreDown",
    "PostDown",
    "SaveConfig",
]

PEER_ATTRIBUTES = [
    "PublicKey",
    "PresharedKeys",
    "AllowedIPs",
    "Endpoint",
    "PersistentKeepalive",
]

KEY_TYPE = {
    "Name": str,
    "Address": list,
    "Endpoint": str,
    "AllowedIPs": list,
    "ListenPort": int,
    "PersistentKeepalive": int,
    "FwMark": str,
    "PrivateKey": str,
    "PresharedKeys": str,
    "DNS": str,
    "MTU": int,
    "Table": str,
    "PreUp": str,
    "PostUp": str,
    "PreDown": str,
    "PostDown": str,
    "SaveConfig": bool,
}


class DatabaseManager:
    def __init__(self, database_path: pathlib.Path):
        self.database_path = database_path
        self.database_template = {"peers": {}}
        self.wireguard = WireGuard()

    def init(self, with_psk: bool):
        """initialize an empty database file"""
        if not self.database_path.exists():
            with self.database_path.open(
                mode="w", encoding="utf-8", newline=""
            ) as database_file:
                writer = csv.DictWriter(
                    database_file, KEY_TYPE.keys(), quoting=csv.QUOTE_ALL
                )
                writer.writeheader()
            print(f"Empty database file {self.database_path} has been created")
        else:
            database = self.read_database()

            # check values that cannot be generated automatically
            for key in ["Address"]:
                for peer in database["peers"]:
                    if database["peers"][peer].get(key) is None:
                        print(f"The value of {key} cannot be automatically generated")
                        sys.exit(1)

            # automatically generate missing values
            # some PSK calculations
            if with_psk:
                psk_needed = sum(range(len(database["peers"])))
                for p in database["peers"]:
                    if database["peers"][p]["PresharedKeys"]:
                        psk_needed -= len(
                            database["peers"][p]["PresharedKeys"].split(",")
                        )
                additional_keys = []
                for _ in range(psk_needed):
                    additional_keys.append(self.wireguard.genkey())

            for counter, peer in enumerate(database["peers"]):
                if database["peers"][peer].get("ListenPort") is None:
                    database["peers"][peer]["ListenPort"] = 51820

                if database["peers"][peer].get("PrivateKey") is None:
                    privatekey = self.wireguard.genkey()
                    database["peers"][peer]["PrivateKey"] = privatekey

                # fill up with additonal PSKS
                if with_psk:
                    peer_needed = len(database["peers"]) - 1 - counter
                    presharedkeys = []
                    if database["peers"][peer]["PresharedKeys"] is not None:
                        presharedkeys.extend(
                            database["peers"][peer]["PresharedKeys"].split(",")
                        )
                    for _ in range(peer_needed - len(presharedkeys)):
                        if additional_keys:
                            presharedkeys.append(additional_keys.pop())
                    database["peers"][peer]["PresharedKeys"] = presharedkeys
            self.write_database(database)

    def read_database(self):
        """read database file into dict

        Returns:
            dict: content of database file in dict format
        """
        if not self.database_path.is_file():
            return self.database_template

        database = copy.deepcopy(self.database_template)

        with self.database_path.open(mode="r", encoding="utf-8") as database_file:
            peers = csv.DictReader(database_file)
            for peer in peers:
                for key in peer:
                    if peer[key] == "":
                        peer[key] = None
                    elif KEY_TYPE[key] == list:
                        peer[key] = peer[key].split(",")
                    elif KEY_TYPE[key] == int:
                        peer[key] = int(peer[key])
                    elif KEY_TYPE[key] == bool:
                        peer[key] = peer[key].lower() == "true"
                database["peers"][peer.pop("Name")] = peer

        return database

    def write_database(self, data: dict):
        """dump data into database file

        Args:
            data (dict): content of database
        """

        with self.database_path.open(
            mode="w", encoding="utf-8", newline=""
        ) as database_file:
            writer = csv.DictWriter(
                database_file, KEY_TYPE.keys(), quoting=csv.QUOTE_ALL
            )
            writer.writeheader()
            data = copy.deepcopy(data)
            for peer in data["peers"]:
                data["peers"][peer]["Name"] = peer
                for key in data["peers"][peer]:
                    if isinstance(data["peers"][peer][key], list):
                        data["peers"][peer][key] = ",".join(data["peers"][peer][key])
                    elif isinstance(data["peers"][peer][key], int):
                        data["peers"][peer][key] = str(data["peers"][peer][key])
                    elif isinstance(data["peers"][peer][key], bool):
                        data["peers"][peer][key] = str(data["peers"][peer][key])
                writer.writerow(data["peers"][peer])

    def addpeer(
        self,
        Name: str,
        Address: list,
        Endpoint: str = None,
        AllowedIPs: list = None,
        ListenPort: int = None,
        PersistentKeepalive: int = None,
        FwMark: str = None,
        PrivateKey: str = None,
        PresharedKeys: str = None,
        DNS: str = None,
        MTU: int = None,
        Table: str = None,
        PreUp: str = None,
        PostUp: str = None,
        PreDown: str = None,
        PostDown: str = None,
        SaveConfig: bool = None,
    ):
        database = self.read_database()

        if Name in database["peers"]:
            print(f"Peer with name {Name} already exists")
            return

        database["peers"][Name] = {}

        # if private key is not specified, generate one
        if locals().get("PrivateKey") is None:
            privatekey = self.wireguard.genkey()
            database["peers"][Name]["PrivateKey"] = privatekey

        for key in INTERFACE_ATTRIBUTES + PEER_ATTRIBUTES:
            if locals().get(key) is not None:
                database["peers"][Name][key] = locals().get(key)

        self.write_database(database)

    def updatepeer(
        self,
        Name: str,
        Address: list = None,
        Endpoint: str = None,
        AllowedIPs: list = None,
        ListenPort: int = None,
        PersistentKeepalive: int = None,
        FwMark: str = None,
        PrivateKey: str = None,
        PresharedKeys: str = None,
        DNS: str = None,
        MTU: int = None,
        Table: str = None,
        PreUp: str = None,
        PostUp: str = None,
        PreDown: str = None,
        PostDown: str = None,
        SaveConfig: bool = None,
    ):
        database = self.read_database()

        if Name not in database["peers"]:
            print(f"Peer with name {Name} does not exist")
            return

        for key in INTERFACE_ATTRIBUTES + PEER_ATTRIBUTES:
            if locals().get(key) is not None:
                database["peers"][Name][key] = locals().get(key)

        self.write_database(database)

    def delpeer(self, Name: str):
        database = self.read_database()

        # abort if user doesn't exist
        if Name not in database["peers"]:
            print(f"Peer with ID {Name} does not exist")
            return

        database["peers"].pop(Name, None)

        # write changes into database
        self.write_database(database)

    def showpeers(self, Name: str, verbose: bool = False):
        database = self.read_database()

        # if name is specified, show the specified peer
        if Name is not None:
            if Name not in database["peers"]:
                print(f"Peer with ID {Name} does not exist")
                return
            peers = [Name]

        # otherwise, show all peers
        else:
            peers = [p for p in database["peers"]]

        field_names = ["Name"]

        # exclude all columns that only have None's in simplified mode
        if verbose is False:
            for peer in peers:
                for key in INTERFACE_ATTRIBUTES + PEER_ATTRIBUTES:
                    if (
                        database["peers"][peer].get(key) is not None
                        and key not in field_names
                    ):
                        field_names.append(key)

        # include all columns by default
        else:
            field_names += INTERFACE_ATTRIBUTES + PEER_ATTRIBUTES

        # create new rich table
        table = Table(show_lines=True)

        # create columns
        for field in field_names:
            table.add_column(
                field,
                style={
                    "Name": "cyan",
                    "Address": "red",
                    "ListenPort": "yellow",
                    "PrivateKey": "magenta",
                    "Endpoint": "green",
                }.get(field),
            )

        # add rows to table
        for peer in peers:
            table.add_row(
                peer,
                *[
                    str(database["peers"][peer].get(k))
                    if not isinstance(database["peers"][peer].get(k), list)
                    else ",".join(database["peers"][peer].get(k))
                    for k in [i for i in field_names if i != "Name"]
                ],
            )

        # print the constructed table in console
        Console().print(table)

    def calculate_psks(self, peers, database):
        inform = 0
        psk_tuples = []
        psk_keys = []
        combinations = list(itertools.combinations(peers, r=2))
        for p in peers:
            if database["peers"][p]["PresharedKeys"] is not None:
                psk_keys.extend(database["peers"][p]["PresharedKeys"].split(","))
        # for "static" behaviour, the first key must used first (.pop(0))
        # reverse to use pop() instead pop(0)
        psk_keys.reverse()
        for combination in combinations:
            if psk_keys:
                psk_tuple = combination + (psk_keys.pop(),)
            else:
                inform += 1
                psk_tuple = combination + (self.wireguard.genkey(),)
            psk_tuples.append(psk_tuple)
        if inform > 0:
            print(
                f'{inform} PSKs generated. They will change every run.\nTo have an more static environment, please run "wg-meshconf --with-psk init" again.'
            )
        return psk_tuples

    def genconfig(self, Name: str, output: pathlib.Path, with_psk: bool):
        database = self.read_database()

        # check if peer ID is specified
        if Name is not None:
            peers = [Name]
        else:
            peers = [p for p in database["peers"]]

        # check if output directory is valid
        # create output directory if it does not exist
        if output.exists() and not output.is_dir():
            print(
                "Error: output path already exists and is not a directory",
                file=sys.stderr,
            )
            raise FileExistsError
        elif not output.exists():
            print(f"Creating output directory: {output}", file=sys.stderr)
            output.mkdir(exist_ok=True)

        if with_psk:
            psk_tuples = self.calculate_psks(peers, database)
        for peer in peers:
            with (output / f"{peer}.conf").open("w") as config:
                config.write("[Interface]\n")
                config.write("# Name: {}\n".format(peer))
                config.write(
                    "Address = {}\n".format(
                        ", ".join(database["peers"][peer]["Address"])
                    )
                )
                config.write(
                    "PrivateKey = {}\n".format(database["peers"][peer]["PrivateKey"])
                )

                for key in INTERFACE_OPTIONAL_ATTRIBUTES:
                    if database["peers"][peer].get(key) is not None:
                        config.write(
                            "{} = {}\n".format(key, database["peers"][peer][key])
                        )

                # generate [Peer] sections for all other peers
                for p in [i for i in database["peers"] if i != peer]:

                    peer_endpoint = database["peers"][p].get("Endpoint")
                    my_endpoint = database["peers"][peer].get("Endpoint")

                    # Clean out the host bit of the Address to use in AllowedIPs
                    peer_subnets = [
                        ipaddress.ip_network(subnet, strict=False)
                        for subnet in database["peers"][p]["Address"]
                    ]

                    # only include peers that can be connected to
                    if peer_endpoint is not None or my_endpoint is not None:
                        config.write("\n[Peer]\n")
                        config.write("# Name: {}\n".format(p))
                        config.write(
                            "PublicKey = {}\n".format(
                                self.wireguard.pubkey(
                                    database["peers"][p]["PrivateKey"]
                                )
                            )
                        )

                        if peer_endpoint is not None:
                            config.write(
                                "Endpoint = {}:{}\n".format(
                                    database["peers"][p]["Endpoint"],
                                    database["peers"][p]["ListenPort"],
                                )
                            )

                        if database["peers"][p].get("Address") is not None:
                            if database["peers"][p].get("AllowedIPs") is not None:
                                allowed_ips = ", ".join(
                                    [str(subnet) for subnet in peer_subnets]
                                    + database["peers"][p]["AllowedIPs"]
                                )
                            else:
                                allowed_ips = ", ".join(
                                    [str(subnet) for subnet in peer_subnets]
                                )
                            config.write("AllowedIPs = {}\n".format(allowed_ips))

                        if (
                            database["peers"][peer].get("PersistentKeepalive")
                            is not None
                        ):
                            config.write(
                                "{} = {}\n".format(
                                    "PersistentKeepalive",
                                    database["peers"][peer]["PersistentKeepalive"],
                                )
                            )

                        if with_psk:
                            for psk_tuple in [x for x in psk_tuples if peer in x]:
                                if p in psk_tuple:
                                    config.write(f"PresharedKey = {psk_tuple[2]}\n")
