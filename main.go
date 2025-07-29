package main

import (
	"fmt"
	"log"
	"net/http" // Standard library package for HTTP servers
)

func main() {
	// Define a simple handler function for the root URL ("/")
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// w is the http.ResponseWriter, used to send the HTTP response
		// r is the *http.Request, which contains details about the incoming request
		fmt.Fprintf(w, "Welcome to the Nurse Booking Backend! Go is running!")
	})

	// Print a message to the console indicating the server is starting
	fmt.Println("Server starting on port 8080...")

	// Start the HTTP server. ListenAndServe blocks until the server stops.
	// The first argument is the address (empty string means all interfaces) and port.
	// The second argument is the handler; nil means use the default ServeMux (which http.HandleFunc registers to).
	log.Fatal(http.ListenAndServe(":8080", nil))
}