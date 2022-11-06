package local

import (
	"context"

	"github.com/docker/docker/api/types/mount"
	"github.com/dstackai/dstackai/runner/internal/artifacts"
)

var _ artifacts.Artifacter = (*Local)(nil)

type Local struct {
	pathLocal string
}

func (l Local) BeforeRun(_ context.Context) error {
	return nil
}

func (l Local) AfterRun(_ context.Context) error {
	return nil
}

func (l Local) DockerBindings(_ string) []mount.Mount {
	return []mount.Mount{
		{
			Type:   mount.TypeBind,
			Source: l.pathLocal,
			Target: l.pathLocal,
		},
	}
}

func NewLocal(path string) *Local {
	return &Local{
		pathLocal: path,
	}
}
