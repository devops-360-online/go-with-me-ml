docker build -t ml-inference:latest . 
because we are using kind by default doesn’t use Docker’s local images.
 kind load docker-image ml-inference:latest