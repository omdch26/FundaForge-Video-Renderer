import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
Config.setOverwriteOutput(true);
// Chromium needs local font files; the Python renderer copies them into
// public/fonts before invoking us.
Config.setChromiumOpenGlRenderer("angle");
