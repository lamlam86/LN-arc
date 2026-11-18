import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "LN-ARC",
  version: packageJson.version,
  copyright: `© ${currentYear}, LN-ARC. Graduation Project.`,
  meta: {
    title: "LN-ARC — Autonomous AI Reconnaissance Console",
    description: "Graduation project: An LLM-driven multi-agent system for autonomous network reconnaissance",
  },
};
