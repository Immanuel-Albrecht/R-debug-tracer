# R-debug-tracer
A python script that automates pressing 's' for step-into while debugging in R, alternating the command with 'where'.

To run, you need to write an R script that sets up your desired environment and defines a function called `debug_main`,
which contains all the code for which you would like to get a 'step-into'-trace. The script should activate debbuging on this function through `debug(debug_main)`. The last command of the script should be `debug_main()`. In order to obtain a trace, you have to start the `R-debug-tracer.py`-script with the setup file path as first parameter. 

The file `debug-demo.r` contains an example of a setup script. In order to invoke the trace and save a copy to a file, you would run

```bash
python3 R-debug-tracer.py debug-demo.r | tee debug-demo.trace
```

from the repository main directory. This produces output similar to

```

R version 3.6.1 (2019-07-05) -- "Action of the Toes"
Copyright (C) 2019 The R Foundation for Statistical Computing
Platform: x86_64-apple-darwin15.6.0 (64-bit)

R is free software and comes with ABSOLUTELY NO WARRANTY.
You are welcome to redistribute it under certain conditions.
Type 'license()' or 'licence()' for distribution details.

  Natural language support but running in an English locale

R is a collaborative project with many contributors.
Type 'contributors()' for more information and
'citation()' on how to cite R or R packages in publications.

Type 'demo()' for some demos, 'help()' for on-line help, or
'help.start()' for an HTML browser interface to help.
Type 'q()' to quit R.

> counts <- c(18,17,15,20,10,20,25,13,12)
> outcome <- gl(3,1,9)
> treatment <- gl(3,3)
> print(d.AD <- data.frame(treatment, outcome, counts))
  treatment outcome counts
1         1       1     18
2         1       2     17
3         1       3     15
4         2       1     20
5         2       2     10
6         2       3     20
7         3       1     25
8         3       2     13
9         3       3     12
> 
> debug_main <- function() {
+     glm.D93 <<- glm(counts ~ outcome + treatment, family = poisson())
+ }
> 
> debug(debug_main)
> 
> debug_main()
debugging in: debug_main()
debug: {
    glm.D93 <<- glm(counts ~ outcome + treatment, family = poisson())
}
Browse[2]> where
where 1: debug_main()

Browse[2]> s
debug: glm.D93 <<- glm(counts ~ outcome + treatment, family = poisson())

[...]

Browse[5]> s
exiting from: vapply(xlev, is.null, NA)
exiting from: .getXlevels(mt, mf)
debug: class(fit) <- c(fit$class, c("glm", "lm"))
Browse[3]> where
where 1: glm(counts ~ outcome + treatment, family = poisson())
where 2: debug_main()

Browse[3]> s
debug: fit
Browse[3]> where
where 1: glm(counts ~ outcome + treatment, family = poisson())
where 2: debug_main()

Browse[3]> s
exiting from: glm(counts ~ outcome + treatment, family = poisson())
exiting from: debug_main()
> q()
```
