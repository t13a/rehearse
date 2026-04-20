FROM node:20-slim

# coreutils ships with the base image (timeout, ls, stat, ...). Add the
# missing pieces of the rehearse toolbox: find/xargs and tree.
#
# This image installs Anthropic's proprietary Claude Code software. Built
# images are intended for local use only. Do not redistribute them unless
# Anthropic's license terms allow it.
RUN apt-get update \
 && apt-get install --no-install-recommends -y ca-certificates curl findutils tree \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://claude.ai/install.sh | bash \
 && mkdir -p /usr/local/share/claude \
 && mv /root/.local/share/claude/versions /usr/local/share/claude/versions \
 && ln -s /usr/local/share/claude/versions/* /usr/local/bin/claude \
 && rm -rf /root/.claude /root/.local

RUN mkdir -p /home/agent

COPY docker/claude/entrypoint.sh /opt/rehearse/entrypoint.sh
RUN chmod +x /opt/rehearse/entrypoint.sh

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
