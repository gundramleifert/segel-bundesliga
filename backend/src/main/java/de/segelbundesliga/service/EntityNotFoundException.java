package de.segelbundesliga.service;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.NOT_FOUND)
public class EntityNotFoundException extends RuntimeException {

    public EntityNotFoundException(String entityName, Long id) {
        super(entityName + " with id " + id + " not found");
    }

    public EntityNotFoundException(String entityName, String field, String value) {
        super(entityName + " with " + field + " '" + value + "' not found");
    }
}
