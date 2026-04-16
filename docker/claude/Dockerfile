FROM node:20-slim

# coreutils ships with the base image (timeout, ls, stat, ...). Add the
# missing pieces of the rehearse toolbox: find/xargs and tree.
RUN apt-get update \
 && apt-get install --no-install-recommends -y findutils tree \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code

RUN mkdir -p /opt/rehearse/scripts /opt/rehearse/prompts /home/agent

COPY docker/claude/entrypoint.sh /opt/rehearse/entrypoint.sh
COPY docker/claude/scripts/ /opt/rehearse/scripts/
COPY prompts/agent.md /opt/rehearse/prompts/agent.md
RUN chmod +x /opt/rehearse/entrypoint.sh

# /opt/rehearse/scripts/ is on PATH so future bash helpers are callable by
# name from the agent's Bash tool.
ENV PATH="/opt/rehearse/scripts:${PATH}"

# Strip the forbidden tools last so the deletion of `rm` itself happens in a
# single invocation (the binary is gone after this RUN finishes).
RUN /usr/bin/rm -f \
    /usr/bin/cp /bin/cp \
    /usr/bin/ln /bin/ln \
    /usr/bin/chmod /bin/chmod \
    /usr/bin/chown /bin/chown \
    /usr/bin/dd /bin/dd \
    /usr/bin/truncate \
    /usr/bin/rm /bin/rm

ENTRYPOINT ["/opt/rehearse/entrypoint.sh"]
