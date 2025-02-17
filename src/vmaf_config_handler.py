# File parsing & handling
import configparser as confp
import logging as lg

# Misc
import math
from pathlib import Path

# Variable typing
from typing import Optional, Union

# Made for this project
from ffmpy_handler import FFmpy_Handler, FFmpy_Handler_Exception
from vmaf_file_handler import VMAF_File_Handler


class VMAF_Config_Handler(VMAF_File_Handler):
    def __init__(
        self,
        args: dict,
        mp_handler: proc_handler,
        log: lg.RootLogger,
        program: Optional[str] = "Calculations",
    ):
        self._args = args
        self._program = program
        self._mp_handler = mp_handler
        self._ffmpy = None
        filename = ""
        if self._args["config"]:
            filename = self._args["config"]
        else:
            filename = "config.ini"

        VMAF_File_Handler.__init__(
            self,
            file=filename,
            file_type="config",
            os_name=self._mp_handler.get_sys_platform(),
            log=log,
        )
        if self._file is not None:
            self._config_data = self._read_config(self._file)
        else:
            self._config_data = self._generate_default_config()
            self._file = "config.ini"
        self._args["config"] = self._file

        self._validate_options(self._file)

    def _generate_default_config_dict(self) -> dict:
        config_dict = {
            "General": {"vmaf_version": 2, "ffmpeg": "ffmpeg"},
            "Calculations": {
                "psnr": False,
                "ssim": False,
                "ms_ssim": False,
                "subsamples": 1,
                "model": "vmaf_v0.6.1",
                "log_path": "vmaf",
                "log_format": "xml",
                "hwaccel": False,
                "threads": self._mp_handler.get_cores_count(),
                "processes": 1,
                "use_remaining_threads": False,
            },
            "Graphing": {
                "output": "vmaf",
                "lower_boundary": "default",
                "custom": 0,
                "threads": self._mp_handler.get_cores_count(),
                "processes": 1,
                "use_remaining_threads": False,
            },
            "Image Settings": {
                "x": 1920.0,
                "y": 1080.0,
                "dpi": 100.0,
                "format": "svg",
                "transparent": True,
            },
            "Video Settings": {
                "x": 1920.0,
                "y": 1080.0,
                "framerate": 60.0,
                "transparent": True,
            },
        }
        return config_dict

    def _generate_default_config(self) -> dict:
        default_config_dict = self._generate_default_config_dict()
        if self._file is None:
            default_config = confp.ConfigParser()
            default_config.read_dict(default_config_dict)

            with open("config.ini", "w") as config_file:
                default_config.write(config_file)

        return default_config_dict

    def _read_config(
        self,
        filename: str,
    ) -> dict:
        config = confp.ConfigParser()
        config.read(filename)

        config_dict = self._generate_default_config_dict()

        self._config_data = dict()

        last_section = None
        try:
            for section, option in config_dict.items():
                last_section = section
                self._config_data[section] = dict()
                for k, v in option.items():
                    try:
                        if type(v) == str:
                            self._config_data[section][k] = config[section].get(k, v)
                        elif type(v) == bool:
                            self._config_data[section][k] = config[section].getboolean(k, v)
                        elif type(v) == int:
                            self._config_data[section][k] = config[section].getint(k, v)
                        elif type(v) == float:
                            self._config_data[section][k] = config[section].getfloat(k, v)
                    except confp.NoOptionError:
                        self._config_data[section][k] = v
        except confp.NoSectionError:
            for k, v in config_dict.items():
                self._config_data[last_section][k] = v

        return self._config_data

    def _validate_options(
        self,
        filename: str,
    ) -> Union[bool, str]:
        """Validate all user specified, config-specified, and remaining default options."""

        def _validate_config_file(filename):
            """Validate the config file."""

            config = None
            file = Path(filename)
            try:
                # Check if path given actually exists
                if file.exists():
                    # Check if path is a file or a directory
                    if file.is_file():
                        config = filename
                    elif file.is_dir():
                        # If user gave a directory instead of a config file,
                        # check if default config file exists in that directory
                        tmp_config = file.joinpath("config.ini")
                        if tmp_config.exists():
                            if tmp_config.is_file():
                                config = tmp_config
                            else:
                                msg = "Could not find config file in directory {} - generating a default one."
                                raise OSError(msg.format(tmp_config))
                        # Otherwise throw an exception
                        else:
                            msg = "Could not find config file in directory {} - generating a default one."
                            raise OSError(msg.format(tmp_config))
                else:
                    msg = "The specified config file {} does not exist - generating a default one."
                    raise OSError(msg.format(filename))
            except OSError as ose:
                self._log.error(ose)

            if config is None:
                return False
            else:
                return config

        def _print_mp_err(
            self,
            var_type: str = "processes",
            cause: str = "User",
        ) -> None:
            msg = "{} specified {} {} which is more than the number of threads the system supports ({})."
            which_dict = None
            if cause == "User":
                which_dict = self._args
            elif cause == "Config file":
                which_dict = self._config_data[self._program]

            self._log.error(
                msg.format(
                    cause,
                    which_dict[var_type],
                    var_type,
                    self._mp_handler.get_cores_count(),
                )
            )

        def _validate_mp(
            self,
            var_type: str = "thread",
        ):
            self._log.info("Validating {} count...".format(var_type))
            type_plural = None
            func = None
            if var_type == "thread":
                type_plural = "threads"
                func = self._mp_handler.set_threads
            else:
                type_plural = "processes"
                func = self._mp_handler.set_procs

            try:
                if self._args[type_plural]:
                    if not func(self._args[type_plural]):
                        _print_mp_err(self, var_type=type_plural, cause="User")
                        msg = "Checking config file for specified {} count."
                        self._log.error(msg.format(var_type))
                        raise HunterAP_Process_Handler_Error()
                    else:
                        self._config_data[self._program][type_plural] = self._args[type_plural]
                else:
                    raise HunterAP_Process_Handler_Error()
            except HunterAP_Process_Handler_Error:
                if int(self._config_data[self._program][type_plural]) > self._mp_handler.get_cores_count():
                    _print_mp_err(self, var_type=type_plural, cause="Config file")
                    msg = "Defaulting to 1 {}."
                    self._log.error(msg.format(var_type))
                    self._config_data[self._program][type_plural] = 1

        def _validate_threads_processes(self) -> None:
            self._log.info("Validating total process count...")
            total = int(self._config_data[self._program]["threads"]) * int(
                self._config_data[self._program]["processes"]
            )
            try:
                if total > self._mp_handler.get_cores_count():
                    msg = "Can not run {0} processes with {1} threads per process as that exceeds the number of threads in the system ({2} threads). Limiting processes down to allow as many processes as possible with {1} threads per process."
                    raise HunterAP_Process_Handler_Error(
                        msg.format(
                            self._config_data[self._program]["processes"],
                            self._config_data[self._program]["threads"],
                            self._mp_handler.get_cores_count(),
                        )
                    )
                else:
                    msg = "Running {0} processes with {1} threads per process. Continuing..."
                    self._log.info(
                        msg.format(
                            self._config_data[self._program]["processes"],
                            self._config_data[self._program]["threads"],
                        )
                    )
            except HunterAP_Process_Handler_Error as hap_phe:
                self._log.error(hap_phe)
                processes = math.floor(
                    self._mp_handler.get_cores_count() / int(self._config_data[self._program]["threads"])
                )
                total_threads = self._config_data[self._program]["threads"] * processes
                rem_threads = self._mp_handler.get_cores_count() - total_threads
                msg = "The program will run {0} processes instead of {1}, with {2} threads per process for a total of {3} total threads in use, with {4} threads remaining unused."
                self._log.error(
                    msg.format(
                        processes,
                        self._config_data[self._program]["processes"],
                        self._config_data[self._program]["threads"],
                        total_threads,
                        rem_threads,
                    )
                )
                self._config_data[self._program]["processes"] = processes

        def _validate_ffmpeg(self) -> None:
            self._log.info("Checking for FFmpeg executable...")

            handler_args = {
                "file_type": "executable",
                "os_name": self._mp_handler.get_sys_platform(),
                "log": self._log,
            }
            if self._args["ffmpeg"]:
                handler_args["file"] = self._args["ffmpeg"]
            else:
                handler_args["file"] = self._config_data["General"]["ffmpeg"]

            self._config_data["General"]["ffmpeg"] = VMAF_File_Handler(**handler_args).get_file()

            try:
                self._ffmpy = FFmpy_Handler(self._config_data["General"]["ffmpeg"], log=self._log)

                has_vmaf = self._ffmpy.search_lib("libvmaf")

                if self._program == "Calculations":
                    if not has_vmaf:
                        msg = 'FFmpeg is not built with VMAF support ("--enable-libvmaf"). The program can not continue and will now exit.'
                        raise OSError(msg)
                msg = 'FFmpeg executable "{}" is valid and contains the libvmaf library. Continuing...'
                self._log.info(msg.format(self._config_data["General"]["ffmpeg"]))
            # except ffmpy.FFExecutableNotFoundError as ffenfe:
            except FFmpy_Handler_Exception as ffenfe:
                # if self._mp_handler.get_sys_platform() == "Windows":
                #     msg = 'FFmpeg executable was not found in given path "{0}".\n'
                #     msg += "FFmpeg is required for this program to run.\n"
                #     msg += "Please make sure you have FFmpeg installed correctly and that you are pointing to the executable through either your config file or through runtime arguments."
                #     self._log.critical(
                #         msg.format(self._config_data["General"]["ffmpeg"])
                #     )
                # else:
                #     self._log.critical(ffenfe)
                exit(1)

        def _validate_model(self) -> None:
            self._log.info("Validating VMAF model file...")
            model_args = {"file_type": "model", "log": self._log}
            if self._args["model"]:
                model_args["file"] = self._args["model"]
            else:
                model_args["file"] = self._config_data["Calculations"]["model"]

            tmp_model = VMAF_File_Handler(**model_args).get_file()

            if self._mp_handler.get_sys_platform() == "Windows":
                if len(Path(tmp_model).resolve().parts) == 1:
                    tmp_model = Path(Path.cwd().joinpath(tmp_model))
                paths = list(Path(tmp_model).resolve().parts)
                drive = paths[0].replace("\\", "")
                paths[0] = drive[0] + r"\\" + drive[1]
                newfile = "/".join(paths)
                tmp_model = newfile
            else:
                if len(Path(tmp_model).resolve().parts) == 1:
                    tmp_model = Path(Path.cwd().joinpath(tmp_model))

            try:
                if self._config_data["General"]["vmaf_version"] == 1:
                    if not tmp_model.endswith(".pkl"):
                        tmp_model += ".pkl"
                else:
                    if not tmp_model.endswith(".json"):
                        tmp_model += ".json"

                output_cmd = "-t 1 -filter_complex "
                output_cmd += repr("libvmaf=model_path={}")
                output_cmd += " -f null"
                out, err = self._ffmpy.run_command(
                    ff_inputs={
                        "video_samples/sample1.mp4": None,
                        "video_samples/sample2.mp4": None,
                    },
                    ff_outputs={"-": output_cmd.format(tmp_model)},
                )

                if "could not read model from path" in err.decode("utf-8"):
                    msg = "Could not find VMAF model file {}."
                    raise FileNotFoundError(msg.format(self._args["model"]))
                else:
                    msg = "VMAF model file {0} is valid for running with VMAF version {1}. Continuing..."
                    self._log.info(
                        msg.format(
                            self._config_data["Calculations"]["model"],
                            self._config_data["General"]["vmaf_version"],
                        )
                    )
                    self._config_data["Calculations"]["model"] = tmp_model
            except FileNotFoundError as fnfe:
                self._log.critical(fnfe)
                exit(1)

        def _validate_log(self) -> None:
            if self._args["log_format"]:
                self._config_data["Calculations"]["log_format"] = self._args["log_format"]

            tmp_log = None
            if self._args["log_path"]:
                tmp_log = VMAF_File_Handler(self._args["log_path"], file_type="log").get_file()
                self._config_data["Calculations"]["log_path"] = tmp_log
                self._config_data["Calculations"]["log_format"] = Path(tmp_log).suffix.replace(".", "")
            else:
                tmp_log = VMAF_File_Handler(
                    self._config_data["Calculations"]["log_path"],
                    file_type="log",
                    log=self._log,
                ).get_file()
                self._config_data["Calculations"]["log_path"] = tmp_log
                self._config_data["Calculations"]["log_format"] = Path(tmp_log).suffix.replace(".", "")

            if self._mp_handler.get_sys_platform() == "Windows":
                if len(Path(tmp_log).resolve().parts) == 1:
                    tmp_log = Path(Path.cwd().joinpath(tmp_log))
                paths = list(Path(tmp_log).resolve().parts)
                drive = paths[0].replace("\\", "")
                paths[0] = drive[0] + r"\\" + drive[1]
                newfile = "/".join(paths)
                self._config_data["Calculations"]["log_path"] = newfile
            else:
                if len(Path(tmp_log).resolve().parts) == 1:
                    tmp_log = Path(Path.cwd().joinpath(tmp_log))

        check = _validate_config_file(filename)
        if check:
            self._read_config(filename)
        else:
            self._generate_default_config()

        # _validate_threads(self)
        #
        # _validate_processes(self)
        _validate_mp(self, var_type="thread")
        _validate_mp(self, var_type="process")

        _validate_threads_processes(self)

        if self._args["vmaf_version"]:
            self._config_data["General"]["vmaf_version"] = self._args["vmaf_version"]

        if self._program == "Calculations":
            _validate_ffmpeg(self)

            if self._args["psnr"]:
                self._config_data["Calculations"]["psnr"] = self._args["psnr"]

            if self._args["ssim"]:
                self._config_data["Calculations"]["ssim"] = self._args["ssim"]

            if self._args["ms_ssim"]:
                self._config_data["Calculations"]["ms_ssim"] = self._args["ms_ssim"]

            if self._args["subsamples"]:
                self._config_data["Calculations"]["subsamples"] = self._args["subsamples"]

            if self._args["hwaccel"]:
                self._config_data["Calculations"]["hwaccel"] = self._args["hwaccel"]

            _validate_model(self)

            _validate_log(self)

    def get_config_data(self) -> dict:
        return self._config_data
