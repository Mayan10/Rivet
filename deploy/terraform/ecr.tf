resource "aws_ecr_repository" "rivet_service" {
  name                 = "rivet-service"
  image_tag_mutability = "IMMUTABLE" # a given tag (e.g. a git sha) always refers to the same build

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "rivet_service" {
  repository = aws_ecr_repository.rivet_service.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 20 images, expire the rest"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
