ARG ELK_VERSION

FROM docker.elastic.co/beats/metricbeat:${ELK_VERSION}
USER root
RUN metricbeat modules enable docker
