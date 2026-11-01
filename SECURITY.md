# Security and private information

Shotdesk 0.1 is a single-user preview. Bind to localhost by default. Use studio access protection and a trusted HTTPS reverse proxy before exposing it to other machines. Model services have their own access boundary; the studio password does not protect their direct ports.

Do not attach API keys, tokens, private settings, full data backups or personal media to public issues. Review diagnostic reports before sharing. If this repository has GitHub private vulnerability reporting enabled, use that channel for security-sensitive reports; otherwise ask the owner for a private contact without publishing exploit details or credentials.

Public packages must be generated with scripts/export_release.py. Do not upload the development folder, local overlay or data volumes.
