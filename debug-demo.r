counts <- c(18,17,15,20,10,20,25,13,12)
outcome <- gl(3,1,9)
treatment <- gl(3,3)
print(d.AD <- data.frame(treatment, outcome, counts))

debug_main <- function() {
    glm.D93 <<- glm(counts ~ outcome + treatment, family = poisson())
}

debug(debug_main)

debug_main()