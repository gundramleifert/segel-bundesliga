package gundramleifert.pairing_list.types;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Arrays;
import java.util.HashMap;

public class Flight {

  @JsonProperty
  public Race[] races;

  private int generation = 0;

  public Flight() {
  }

  public Flight(Race[] races) {
    this.races = races;
  }

  public Flight copy() {
    Race[] races = new Race[this.races.length];
    for (int i = 0; i < races.length; i++) {
      races[i] = this.races[i].copy();
    }
    return new Flight(races);
  }

  public void getOlder() {
    generation++;
  }

  public int getAge() {
    return generation;
  }

//  public int diffNumTeams() {
//    int num = races[0].teams.length;
//    int min = num;
//    int max = num;
//    for (int i = 1; i < races.length; i++) {
//      num = races[i].teams.length;
//      min = Math.min(min, num);
//      max = Math.max(max, num);
//    }
//    return max-min;
//
//  }

  public void resetAge() {
    generation = 0;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;

    Flight flight = (Flight) o;

    // Probably incorrect - comparing Object[] arrays with Arrays.equals
    return Arrays.equals(races, flight.races);
  }

  @Override
  public int hashCode() {
    return Arrays.hashCode(races);
  }
}
