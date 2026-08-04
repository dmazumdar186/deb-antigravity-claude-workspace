import { Config } from "remotion";

// Alpha-capable defaults so overlay renders work out of the box.
// See directives/video/remotion_render.md for preset switching.
Config.setVideoImageFormat("png");
Config.setChromiumOpenGlRenderer("angle");
