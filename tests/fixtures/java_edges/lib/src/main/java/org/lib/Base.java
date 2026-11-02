package org.lib;

public abstract class Base {
    public abstract void step();

    public void greet() {
        System.out.println("hello");
    }

    public void tick() {
        step();
    }
}
