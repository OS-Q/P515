from platform import system

from platformio.managers.platform import PlatformBase
from platformio.util import get_systype

class P515Platform(PlatformBase):

    def configure_default_packages(self, variables, targets):
        board = variables.get("board")
        build_core = variables.get(
            "board_build.core", self.board_config(variables.get("board")).get(
                "build.core", "arduino"))

        if "arduino" in variables.get("pioframework", []):
            # force older compiler; necessary for this arduino framework...
            #self.packages["toolchain-gccarmnoneeabi"]["version"] = "~1.40804.0"
            #self.packages["toolchain-gccarmnoneeabi"]["version"] = "~1.50401.0"
            #self.packages["toolchain-gccarmnoneeabi"]["version"] = "~1.70201.0"
            #self.packages["toolchain-gccarmnoneeabi"]["version"] = "~1.90201.0"
            self.packages["toolchain-gccarmnoneeabi"]["version"] = "~1.40903.0"
            self.frameworks['arduino']['package'] = "framework-arduino-w60x"
            self.packages['framework-arduino-w60x']['optional'] = False

        default_protocol = self.board_config(variables.get(
            "board")).get("upload.protocol") or ""
        if variables.get("upload_protocol", default_protocol) == "dfu":
            self.packages["tool-dfuutil"]["optional"] = False

        # configure J-LINK tool
        jlink_conds = [
            "jlink" in variables.get(option, "")
            for option in ("upload_protocol", "debug_tool")
        ]
        if variables.get("board"):
            board_config = self.board_config(variables.get("board"))
            jlink_conds.extend([
                "jlink" in board_config.get(key, "")
                for key in ("debug.default_tools", "upload.protocol")
            ])
        jlink_pkgname = "tool-jlink"
        if not any(jlink_conds) and jlink_pkgname in self.packages:
            del self.packages[jlink_pkgname]

        return PlatformBase.configure_default_packages(self, variables,
                                                       targets)

    def get_boards(self, id_=None):
        result = PlatformBase.get_boards(self, id_)
        if not result:
            return result
        if id_:
            return self._add_default_debug_tools(result)
        else:
            for key, value in result.items():
                result[key] = self._add_default_debug_tools(result[key])
        return result

    def _add_default_debug_tools(self, board):
        debug = board.manifest.get("debug", {})
        upload_protocols = board.manifest.get("upload", {}).get(
            "protocols", [])
        if "tools" not in debug:
            debug['tools'] = {}

        # BlackMagic, J-Link, ST-Link
        for link in ("blackmagic", "jlink", "stlink", "cmsis-dap"):
            if link not in upload_protocols or link in debug['tools']:
                continue
            if link == "blackmagic":
                debug['tools']['blackmagic'] = {
                    "hwids": [["0x1d50", "0x6018"]],
                    "require_debug_port": True
                }
            elif link == "jlink":
                assert debug.get("jlink_device"), (
                    "Missed J-Link Device ID for %s" % board.id)
                debug['tools'][link] = {
                    "server": {
                        "package": "tool-jlink",
                        "arguments": [
                            "-singlerun",
                            "-if", "SWD",
                            "-select", "USB",
                            "-device", debug.get("jlink_device"),
                            "-port", "2331"
                        ],
                        "executable": ("JLinkGDBServerCL.exe"
                                       if system() == "Windows" else
                                       "JLinkGDBServer")
                    }
                }
            else:
                server_args = ["-s", "$PACKAGE_DIR/scripts"]
                if debug.get("openocd_board"):
                    server_args.extend([
                        "-f", "board/%s.cfg" % debug.get("openocd_board")
                    ])
                else:
                    assert debug.get("openocd_target"), (
                        "Missed target configuration for %s" % board.id)
                    server_args.extend([
                        "-f", "interface/%s.cfg" % link,
                        "-c", "transport select %s" % (
                            "hla_swd" if link == "stlink" else "swd"),
                        "-f", "target/%s.cfg" % debug.get("openocd_target")
                    ])
                    server_args.extend(debug.get("openocd_extra_args", []))

                debug['tools'][link] = {
                    "server": {
                        "package": "tool-openocd-w60x",
                        "executable": "bin/openocd",
                        "arguments": server_args
                    }
                }
            debug['tools'][link]['onboard'] = link in debug.get("onboard_tools", [])
            debug['tools'][link]['default'] = link in debug.get("default_tools", [])

        board.manifest['debug'] = debug
        return board
