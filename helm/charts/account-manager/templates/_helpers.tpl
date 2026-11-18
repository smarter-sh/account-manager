{{/*
The directories that the processes of the Account Manager image write at runtime. Every
other path in the image is read-only: global.containerSecurityContext.readOnlyRootFilesystem
makes the whole root filesystem read-only, and the static files are collected into the
image when it is built. Each of these is an emptyDir, which, like the container's own
filesystem, lasts as long as the pod.

- /tmp: temporary files, e.g. the init job's log
- .cache: python packages' caches
- data/celery: celery beat's schedule file
- data/media: Django's media storage, when the environment is not configured for S3
*/}}
{{- define "am.writableVolumes" -}}
- name: am-tmp
  emptyDir: {}
- name: am-cache
  emptyDir: {}
- name: am-data-celery
  emptyDir: {}
- name: am-data-media
  emptyDir: {}
{{- end }}

{{- define "am.writableVolumeMounts" -}}
- name: am-tmp
  mountPath: /tmp
- name: am-cache
  mountPath: /home/am_user/.cache
- name: am-data-celery
  mountPath: /home/am_user/data/celery
- name: am-data-media
  mountPath: /home/am_user/data/media
{{- end }}

{{/*
The Docker image of every pod: env.AM_DOCKER_IMAGE, which the deploy action sets, or else
global.image.repository:global.image.tag.
*/}}
{{- define "am.image" -}}
{{- if .Values.env.AM_DOCKER_IMAGE -}}
{{- .Values.env.AM_DOCKER_IMAGE -}}
{{- else -}}
{{- $repository := required "set env.AM_DOCKER_IMAGE, or global.image.repository and global.image.tag" .Values.global.image.repository -}}
{{- $tag := required "set env.AM_DOCKER_IMAGE, or global.image.repository and global.image.tag" .Values.global.image.tag -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
The labels that every resource of the chart carries. The caller adds app.kubernetes.io/name
and, for a pod, app.kubernetes.io/component.
*/}}
{{- define "am.commonLabels" -}}
helm.sh/chart: "{{ .Chart.Name }}-{{ .Chart.Version }}"
app.kubernetes.io/application-group: "{{ .Values.global.appName }}"
{{- end }}
