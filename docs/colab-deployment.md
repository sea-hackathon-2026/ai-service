# Colab GPU Deployment

`notebooks/ai_service_colab.ipynb` is the only supported notebook. It installs
the AI API dependency set, optionally prepares Wav2Lip, asks for secrets with
`getpass`, starts `services.ai_api.main:app`, and publishes port 8000 through
ngrok.

Use it for demos and GPU experiments. Do not treat it as production hosting:
the URL, process, filesystem, and GPU allocation are ephemeral. Keep source code
in the repository and move reusable notebook logic into service modules.

Before running:

1. Select a GPU runtime.
2. Verify the repository URL in the clone cell.
3. Provide a random client API key.
4. Provide Gemini and ngrok credentials only when those adapters are required.
5. If Wav2Lip is enabled, place the checkpoint at the configured path and set
   `AI_API_LIVESTREAM_ENABLE_WAV2LIP=true`.
