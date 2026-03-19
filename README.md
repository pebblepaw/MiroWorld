## **AI Consultant with Synthetic Population Simulation (Singapore-Centric)**

Traditional methods of gauging public sentiment—surveys, focus groups, and town halls—are slow, expensive, and increasingly unreliable due to declining participation rates and response biases. In Singapore's fast-paced policy and business landscape, decision-makers need a way to stress-test their ideas against a realistic cross-section of the population *before* committing resources to a full public rollout.

This project addresses that gap by building **McKAInsey**, a cloud-native AI consulting platform that simulates how the Singaporean populace would respond to proposed government policies or corporate marketing campaigns. The system is grounded in the **NVIDIA Nemotron-Personas-Singapore** dataset—**888,000 unique synthetic personas** mapped across **38 demographic and contextual fields**, covering all 55 planning areas, multi-ethnic and multi-religious identities, income brackets, occupations, and digital literacy levels, all statistically calibrated to the 2024 Singapore Census.

The platform deploys **multi-agent LLM simulations** where dozens of these personas are instantiated as autonomous AI agents. These agents don't just answer survey questions—they *react*, *debate each other in digital forums*, and *change their minds* based on peer influence, mirroring how real public opinion forms through social interaction. The result is a dynamic simulation that surfaces not just approval ratings, but the **specific friction points, demographic fault lines, and persuasion pathways** within a target population.

## Quick Start (Demo + Live on One Site)

Use the launcher from repo root:

```bash
./quick_start.sh --mode auto
```

You can also call it explicitly with Bash:

```bash
bash ./quick_start.sh --mode auto
```

`bash` is the shell interpreter that runs the script file. In this project, `./quick_start.sh ...` and `bash ./quick_start.sh ...` are equivalent.

### Mode Behavior

- `--mode auto` (default): live backend first, then demo-cache fallback.
- `--mode demo`: demo-cache first, then live fallback.
- `--mode live`: live backend first, then demo-cache fallback.

Both forms are supported:

- `--mode demo`
- `--mode=demo`

### Optional Flags

- `--refresh-demo`: regenerate demo cache before boot.
- `--real-oasis`: enable native OASIS sidecar runtime paths.

### Common Startup Issue (Ports In Use)

If startup fails due ports already occupied:

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill
lsof -tiTCP:5173 -sTCP:LISTEN | xargs kill
```
