package org.lib;

/** Nothing in the tree implements this: a framework writes it at run time. */
public interface Repo {
    String find(int id);
}
