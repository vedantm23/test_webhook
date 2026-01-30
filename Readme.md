# PROJECT DESCRPTION
GitHub Webhook Activity Monitor is a real-time event tracking application built using Flask and MongoDB for the backend, with frontend file index.html to display event data. The application listens to GitHub webhook events such as push, pull request, and merge activities, processes the payload, and stores structured data in MongoDB.
The index.html file dynamically fetches event data from the backend API at regular intervals (every 15 seconds) and updates the UI in real time.

# HOW TO RUN PROJECT
To run the project, clone the repository, install the required dependencies, start MongoDB, and run the Flask server. For webhook testing, ngrok is used to expose the local server to GitHub and trigger events.

This project demonstrates webhook integration, REST API development, MongoDB data handling, and real-time frontend updates using a simple and clean structure.
