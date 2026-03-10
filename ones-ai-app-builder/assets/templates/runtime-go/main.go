package main

import (
	"encoding/json"
	"net/http"
	"os"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"runtime":        "go122",
			"appId":          valueOrDefault("APP_ID", "unknown"),
			"dataDir":        valueOrDefault("APP_DATA_DIR", "/data"),
			"releaseVersion": valueOrDefault("RELEASE_VERSION", "dev"),
		})
	})
	_ = http.ListenAndServe("0.0.0.0:"+port, nil)
}

func valueOrDefault(key string, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
