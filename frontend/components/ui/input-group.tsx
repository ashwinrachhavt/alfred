import * as React from "react"

import { cn } from "@/lib/utils"

type InputGroupProps = React.ComponentPropsWithoutRef<"div">

const InputGroup = React.forwardRef<React.ElementRef<"div">, InputGroupProps>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        data-slot="input-group"
        className={cn("flex w-full items-stretch", className)}
        {...props}
      />
    )
  }
)
InputGroup.displayName = "InputGroup"

type InputGroupAddonProps = React.ComponentPropsWithoutRef<"div">

const InputGroupAddon = React.forwardRef<React.ElementRef<"div">, InputGroupAddonProps>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        data-slot="input-group-addon"
        className={cn(
          "inline-flex items-center rounded-md border border-r-0 bg-muted px-2 text-sm text-muted-foreground",
          className
        )}
        {...props}
      />
    )
  }
)
InputGroupAddon.displayName = "InputGroupAddon"

export { InputGroup, InputGroupAddon }
